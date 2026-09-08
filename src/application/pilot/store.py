"""Catálogo imutável de snapshots e persistência local do piloto."""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from application.pilot.models import (
    CoverageIndicator,
    FeedbackRecord,
    PilotRun,
    RunStatus,
    RunSummary,
    SnapshotQuality,
    SnapshotSummary,
)
from domain.planning.adjustments import PlanningConstraints, ScheduleAdjustment
from domain.planning.config import PlanningConfig
from domain.planning.entities import (
    HumanDecision,
    PlanningRequest,
    PlanningSnapshot,
    PlanningStageTrace,
)

_MAX_SNAPSHOT_BYTES = 256 * 1024 * 1024
_INTERRUPTED_ERROR = "run interrupted by pilot service restart"


class SnapshotCatalogError(ValueError):
    """O catálogo contém um snapshot inseguro, inválido ou ambíguo."""


class SnapshotChangedError(RuntimeError):
    """Um arquivo congelado foi alterado após entrar no catálogo."""


class PilotStore(Protocol):
    def initialize(self) -> None: ...

    def create_run(self, run: PilotRun) -> None: ...

    def mark_running(self, run_id: str, started_at: datetime) -> PilotRun: ...

    def update_progress(self, run_id: str, event: PlanningStageTrace) -> PilotRun: ...

    def mark_completed(
        self,
        run_id: str,
        *,
        completed_at: datetime,
        proposal_id: str,
        summary: RunSummary,
        trace_events: tuple[PlanningStageTrace, ...],
        artifact_names: tuple[str, ...],
    ) -> PilotRun: ...

    def mark_failed(self, run_id: str, *, completed_at: datetime, error: str) -> PilotRun: ...

    def recover_interrupted(self, at: datetime) -> int: ...

    def get_run(self, run_id: str) -> PilotRun | None: ...

    def list_runs(self, status: RunStatus | None = None) -> tuple[PilotRun, ...]: ...

    def save_decision(
        self,
        run_id: str,
        decision: HumanDecision,
        summary: RunSummary,
    ) -> PilotRun: ...

    def add_feedback(self, records: Sequence[FeedbackRecord]) -> None: ...

    def list_feedback(self, run_id: str | None = None) -> tuple[FeedbackRecord, ...]: ...

    def append_adjustment(
        self, run_id: str, adjustment: ScheduleAdjustment
    ) -> tuple[ScheduleAdjustment, ...]: ...

    def pop_last_adjustment(self, run_id: str) -> tuple[ScheduleAdjustment, ...]: ...

    def list_adjustments(self, run_id: str) -> tuple[ScheduleAdjustment, ...]: ...

    def save_constraints(self, run_id: str, constraints: PlanningConstraints) -> None: ...

    def get_constraints(self, run_id: str) -> PlanningConstraints: ...


def _coverage(key: str, present: int, total: int) -> CoverageIndicator:
    missing = total - present
    percentage = 0.0 if total == 0 else round(present / total * 100, 2)
    return CoverageIndicator(
        key=key,
        present=present,
        total=total,
        missing=missing,
        coverage_percent=percentage,
    )


def _rejected_count(metadata: dict[str, Any]) -> int:
    for key in ("rejected_record_count", "rejected_records_count", "rejected_records"):
        value = metadata.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return max(0, value)
        if isinstance(value, (list, tuple)):
            return len(value)
        if isinstance(value, dict):
            count = value.get("count")
            if isinstance(count, int) and not isinstance(count, bool):
                return max(0, count)
    return 0


# Limite semanal da CLT para jornada normal. Escala declarada acima disso não é
# erro de alocação: é o cadastro afirmando uma jornada que não existe, e quem
# recebe a proposta precisa saber disso antes de julgá-la.
WEEKLY_HOURS_LIMIT = 44.0


def _weekly_minutes_by_worker(snapshot: PlanningSnapshot) -> dict[str, float]:
    minutes: dict[str, float] = {}
    for slot in snapshot.availability:
        duration = (slot.window.end - slot.window.start).total_seconds() / 60
        minutes[slot.worker_id] = minutes.get(slot.worker_id, 0.0) + duration
    return minutes


def snapshot_quality(snapshot: PlanningSnapshot) -> SnapshotQuality:
    operations = snapshot.operations
    referenced_asset_ids = {
        operation.asset_id for operation in operations if operation.asset_id is not None
    }
    critical_asset_ids = {
        operation.asset_id
        for operation in operations
        if operation.asset_id is not None and operation.criticality is not None
    }
    worker_ids_with_availability = {slot.worker_id for slot in snapshot.availability}
    active_worker_ids = {worker.worker_id for worker in snapshot.workers if worker.active}
    available_workers = len(worker_ids_with_availability & active_worker_ids)
    material_requirement_count = sum(
        len(operation.required_materials) for operation in operations
    )
    weekly_minutes = _weekly_minutes_by_worker(snapshot)
    indicators = (
        _coverage(
            "operations_with_priority",
            sum(operation.priority_level is not None for operation in operations),
            len(operations),
        ),
        _coverage(
            "operations_with_sla",
            sum(operation.due_at is not None for operation in operations),
            len(operations),
        ),
        _coverage(
            "assets_with_criticality",
            len(critical_asset_ids),
            len(referenced_asset_ids),
        ),
        _coverage(
            "operations_with_planned_duration",
            sum(operation.planned_duration_minutes is not None for operation in operations),
            len(operations),
        ),
        _coverage(
            "operations_with_materials",
            sum(bool(operation.required_materials) for operation in operations),
            len(operations),
        ),
        _coverage(
            "operations_with_activity_type",
            sum(operation.activity_type_id is not None for operation in operations),
            len(operations),
        ),
        _coverage("workers_with_availability", available_workers, len(active_worker_ids)),
        _coverage(
            "workers_within_weekly_hours",
            sum(
                minutes / 60 <= WEEKLY_HOURS_LIMIT
                for worker_id, minutes in weekly_minutes.items()
                if worker_id in active_worker_ids
            ),
            len([worker_id for worker_id in weekly_minutes if worker_id in active_worker_ids]),
        ),
    )
    return SnapshotQuality(
        operation_count=len(operations),
        historical_execution_count=len(snapshot.history),
        inventory_item_count=len(snapshot.inventory),
        worker_count=len(snapshot.workers),
        availability_slot_count=len(snapshot.availability),
        material_requirement_count=material_requirement_count,
        rejected_record_count=_rejected_count(snapshot.metadata),
        indicators=indicators,
    )


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SnapshotCatalogError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _validate_snapshot_id(snapshot_id: str) -> None:
    if (
        not snapshot_id
        or "\x00" in snapshot_id
        or "/" in snapshot_id
        or "\\" in snapshot_id
        or snapshot_id in {".", ".."}
    ):
        raise SnapshotCatalogError("snapshot_id contains an unsafe path component")


class SnapshotCatalog:
    """Indexa arquivos JSON diretos e detecta qualquer alteração posterior."""

    def __init__(self, root: Path, *, max_bytes: int = _MAX_SNAPSHOT_BYTES) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        root.mkdir(parents=True, exist_ok=True)
        self._root = root.resolve()
        self._max_bytes = max_bytes
        self._paths: dict[str, Path] = {}
        self._digests: dict[str, str] = {}
        self._snapshots: dict[str, PlanningSnapshot] = {}
        self._summaries: dict[str, SnapshotSummary] = {}
        self._index()

    def _index(self) -> None:
        for path in sorted(self._root.iterdir(), key=lambda item: item.name):
            if path.suffix.lower() != ".json":
                continue
            if path.is_symlink():
                raise SnapshotCatalogError(f"snapshot symlink is not allowed: {path.name}")
            resolved = path.resolve()
            if resolved.parent != self._root or not resolved.is_file():
                raise SnapshotCatalogError(f"snapshot path is not a direct file: {path.name}")
            raw = self._read_bounded(resolved)
            digest = hashlib.sha256(raw).hexdigest()
            snapshot = self._validate(raw, path.name)
            _validate_snapshot_id(snapshot.snapshot_id)
            if snapshot.snapshot_id in self._paths:
                raise SnapshotCatalogError(
                    f"duplicate snapshot_id in catalog: {snapshot.snapshot_id}"
                )
            metadata = snapshot.metadata
            source = metadata.get("source")
            latest_ingestion = metadata.get("latest_ingestion")
            summary = SnapshotSummary(
                snapshot_id=snapshot.snapshot_id,
                tenant_id=snapshot.tenant_id,
                as_of=snapshot.as_of,
                schema_version=snapshot.schema_version,
                sha256=digest,
                size_bytes=len(raw),
                source=source if isinstance(source, str) else None,
                latest_ingestion=(
                    latest_ingestion if isinstance(latest_ingestion, str) else None
                ),
                quality=snapshot_quality(snapshot),
            )
            self._paths[snapshot.snapshot_id] = resolved
            self._digests[snapshot.snapshot_id] = digest
            self._snapshots[snapshot.snapshot_id] = snapshot
            self._summaries[snapshot.snapshot_id] = summary

    def _read_bounded(self, path: Path) -> bytes:
        size = path.stat().st_size
        if size <= 0 or size > self._max_bytes:
            raise SnapshotCatalogError(f"snapshot size is outside the allowed limit: {path.name}")
        raw = path.read_bytes()
        if len(raw) != size:
            raise SnapshotCatalogError(f"snapshot changed while being read: {path.name}")
        return raw

    @staticmethod
    def _validate(raw: bytes, name: str) -> PlanningSnapshot:
        try:
            payload = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_object_without_duplicate_keys,
            )
            if not isinstance(payload, dict):
                raise SnapshotCatalogError("snapshot JSON root must be an object")
            return PlanningSnapshot.model_validate(payload)
        except SnapshotCatalogError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
            raise SnapshotCatalogError(f"invalid canonical snapshot: {name}") from exc

    def list(self) -> tuple[SnapshotSummary, ...]:
        return tuple(
            self._summaries[key]
            for key in sorted(
                self._summaries,
                key=lambda item: (
                    self._summaries[item].as_of,
                    item,
                ),
                reverse=True,
            )
        )

    def get(self, snapshot_id: str) -> PlanningSnapshot:
        _validate_snapshot_id(snapshot_id)
        path = self._paths.get(snapshot_id)
        if path is None:
            raise KeyError(f"snapshot not found: {snapshot_id}")
        if path.is_symlink() or path.resolve().parent != self._root:
            raise SnapshotChangedError("frozen snapshot path changed")
        raw = self._read_bounded(path)
        actual = hashlib.sha256(raw).hexdigest()
        if not hmac.compare_digest(actual, self._digests[snapshot_id]):
            raise SnapshotChangedError("frozen snapshot content changed")
        return self._snapshots[snapshot_id]


class SQLitePilotStore:
    """Store local e autocontido; não possui qualquer conexão com a origem."""

    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        if database_path.is_symlink():
            raise ValueError("pilot database cannot be a symlink")
        self._database_path = database_path.resolve()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS pilot_runs (
                    run_id TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('queued', 'running', 'completed', 'failed', 'interrupted')
                    ),
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    request_json TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    proposal_id TEXT,
                    summary_json TEXT,
                    error TEXT,
                    current_stage TEXT,
                    trace_json TEXT NOT NULL DEFAULT '[]',
                    artifact_names_json TEXT NOT NULL DEFAULT '[]',
                    adjustments_json TEXT NOT NULL DEFAULT '[]',
                    constraints_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_pilot_runs_created
                    ON pilot_runs(created_at DESC, run_id);
                CREATE INDEX IF NOT EXISTS idx_pilot_runs_status
                    ON pilot_runs(status, created_at DESC);

                CREATE TABLE IF NOT EXISTS pilot_decisions (
                    run_id TEXT PRIMARY KEY REFERENCES pilot_runs(run_id),
                    snapshot_id TEXT NOT NULL,
                    proposal_id TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    decided_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS pilot_feedback (
                    feedback_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES pilot_runs(run_id),
                    snapshot_id TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    skill TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    recorded_by TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_pilot_feedback_golden_set
                    ON pilot_feedback(snapshot_id, operation_id, skill, verdict);
                CREATE INDEX IF NOT EXISTS idx_pilot_feedback_run
                    ON pilot_feedback(run_id, recorded_at, feedback_id);
                """
            )
            # `CREATE TABLE IF NOT EXISTS` cobre banco novo, mas não acrescenta
            # coluna a uma tabela `pilot_runs` que já existia antes desta
            # migração — e o piloto tem banco assim em produção. `initialize()`
            # roda em todo boot, então o `ALTER TABLE` tem que ser condicional
            # ao que já está no schema (via `PRAGMA table_info`) para não
            # estourar `duplicate column name` na segunda vez que rodar sobre
            # o mesmo arquivo.
            existing_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(pilot_runs)")
            }
            if "adjustments_json" not in existing_columns:
                connection.execute(
                    "ALTER TABLE pilot_runs ADD COLUMN adjustments_json"
                    " TEXT NOT NULL DEFAULT '[]'"
                )
            if "constraints_json" not in existing_columns:
                connection.execute("ALTER TABLE pilot_runs ADD COLUMN constraints_json TEXT")
            connection.execute("PRAGMA user_version = 1")

    def create_run(self, run: PilotRun) -> None:
        if run.status is not RunStatus.QUEUED:
            raise ValueError("new pilot run must start queued")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO pilot_runs (
                    run_id, snapshot_id, tenant_id, status, created_at,
                    request_json, config_json, trace_json, artifact_names_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '[]', '[]')
                """,
                (
                    run.run_id,
                    run.snapshot_id,
                    run.tenant_id,
                    run.status.value,
                    run.created_at.isoformat(),
                    run.request.model_dump_json(),
                    run.config.model_dump_json(),
                ),
            )

    def mark_running(self, run_id: str, started_at: datetime) -> PilotRun:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE pilot_runs
                   SET status = ?, started_at = ?, error = NULL
                 WHERE run_id = ? AND status = ?
                """,
                (
                    RunStatus.RUNNING.value,
                    started_at.isoformat(),
                    run_id,
                    RunStatus.QUEUED.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("run is not queued")
        run = self.get_run(run_id)
        assert run is not None
        return run

    def update_progress(self, run_id: str, event: PlanningStageTrace) -> PilotRun:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status, trace_json FROM pilot_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"run not found: {run_id}")
            if row["status"] != RunStatus.RUNNING.value:
                raise ValueError("only a running run can report progress")
            events = json.loads(str(row["trace_json"]))
            if events and event.sequence <= int(events[-1]["sequence"]):
                raise ValueError("trace sequence must increase")
            events.append(event.model_dump(mode="json"))
            connection.execute(
                """
                UPDATE pilot_runs
                   SET current_stage = ?, trace_json = ?
                 WHERE run_id = ? AND status = ?
                """,
                (
                    event.stage,
                    json.dumps(events, ensure_ascii=False, separators=(",", ":")),
                    run_id,
                    RunStatus.RUNNING.value,
                ),
            )
        run = self.get_run(run_id)
        assert run is not None
        return run

    def mark_completed(
        self,
        run_id: str,
        *,
        completed_at: datetime,
        proposal_id: str,
        summary: RunSummary,
        trace_events: tuple[PlanningStageTrace, ...],
        artifact_names: tuple[str, ...],
    ) -> PilotRun:
        trace_json = json.dumps(
            [event.model_dump(mode="json") for event in trace_events],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        current_stage = trace_events[-1].stage if trace_events else None
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE pilot_runs
                   SET status = ?, completed_at = ?, proposal_id = ?,
                       summary_json = ?, error = NULL, current_stage = ?,
                       trace_json = ?, artifact_names_json = ?
                 WHERE run_id = ? AND status = ?
                """,
                (
                    RunStatus.COMPLETED.value,
                    completed_at.isoformat(),
                    proposal_id,
                    summary.model_dump_json(),
                    current_stage,
                    trace_json,
                    json.dumps(artifact_names, ensure_ascii=False),
                    run_id,
                    RunStatus.RUNNING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("run is not running")
        run = self.get_run(run_id)
        assert run is not None
        return run

    def mark_failed(self, run_id: str, *, completed_at: datetime, error: str) -> PilotRun:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE pilot_runs
                   SET status = ?, completed_at = ?, error = ?
                 WHERE run_id = ? AND status IN (?, ?)
                """,
                (
                    RunStatus.FAILED.value,
                    completed_at.isoformat(),
                    error,
                    run_id,
                    RunStatus.QUEUED.value,
                    RunStatus.RUNNING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("run is not active")
        run = self.get_run(run_id)
        assert run is not None
        return run

    def recover_interrupted(self, at: datetime) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE pilot_runs
                   SET status = ?, completed_at = ?, error = ?
                 WHERE status IN (?, ?)
                """,
                (
                    RunStatus.INTERRUPTED.value,
                    at.isoformat(),
                    _INTERRUPTED_ERROR,
                    RunStatus.QUEUED.value,
                    RunStatus.RUNNING.value,
                ),
            )
            return cursor.rowcount

    def get_run(self, run_id: str) -> PilotRun | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT r.*, d.decision_json
                  FROM pilot_runs r
                  LEFT JOIN pilot_decisions d ON d.run_id = r.run_id
                 WHERE r.run_id = ?
                """,
                (run_id,),
            ).fetchone()
        return None if row is None else self._row_to_run(row)

    def list_runs(self, status: RunStatus | None = None) -> tuple[PilotRun, ...]:
        sql = """
            SELECT r.*, d.decision_json
              FROM pilot_runs r
              LEFT JOIN pilot_decisions d ON d.run_id = r.run_id
        """
        params: tuple[str, ...] = ()
        if status is not None:
            sql += " WHERE r.status = ?"
            params = (status.value,)
        sql += " ORDER BY r.created_at DESC, r.run_id"
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return tuple(self._row_to_run(row) for row in rows)

    def save_decision(
        self,
        run_id: str,
        decision: HumanDecision,
        summary: RunSummary,
    ) -> PilotRun:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT snapshot_id, proposal_id, status FROM pilot_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"run not found: {run_id}")
            if row["status"] != RunStatus.COMPLETED.value:
                raise ValueError("only a completed run can receive a decision")
            if row["proposal_id"] != decision.proposal_id:
                raise ValueError("decision does not reference the run proposal")
            try:
                connection.execute(
                    """
                    INSERT INTO pilot_decisions (
                        run_id, snapshot_id, proposal_id, decision_json, decided_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        str(row["snapshot_id"]),
                        decision.proposal_id,
                        decision.model_dump_json(),
                        decision.decided_at.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("run already has a human decision") from exc
            connection.execute(
                "UPDATE pilot_runs SET summary_json = ? WHERE run_id = ?",
                (summary.model_dump_json(), run_id),
            )
        run = self.get_run(run_id)
        assert run is not None
        return run

    def add_feedback(self, records: Sequence[FeedbackRecord]) -> None:
        if not records:
            return
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO pilot_feedback (
                    feedback_id, run_id, snapshot_id, operation_id, skill,
                    verdict, reason, recorded_by, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(
                    (
                        record.feedback_id,
                        record.run_id,
                        record.snapshot_id,
                        record.operation_id,
                        record.skill.value,
                        record.verdict.value,
                        record.reason,
                        record.recorded_by,
                        record.recorded_at.isoformat(),
                    )
                    for record in records
                ),
            )

    def list_feedback(self, run_id: str | None = None) -> tuple[FeedbackRecord, ...]:
        sql = "SELECT * FROM pilot_feedback"
        params: tuple[str, ...] = ()
        if run_id is not None:
            sql += " WHERE run_id = ?"
            params = (run_id,)
        sql += " ORDER BY recorded_at, feedback_id"
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return tuple(
            FeedbackRecord(
                feedback_id=str(row["feedback_id"]),
                run_id=str(row["run_id"]),
                snapshot_id=str(row["snapshot_id"]),
                operation_id=str(row["operation_id"]),
                skill=str(row["skill"]),
                verdict=str(row["verdict"]),
                reason=str(row["reason"]),
                recorded_by=str(row["recorded_by"]),
                recorded_at=datetime.fromisoformat(str(row["recorded_at"])),
            )
            for row in rows
        )

    @staticmethod
    def _load_adjustments(row: sqlite3.Row) -> list[ScheduleAdjustment]:
        return [
            ScheduleAdjustment.model_validate(item)
            for item in json.loads(str(row["adjustments_json"]))
        ]

    @staticmethod
    def _dump_adjustments(adjustments: Sequence[ScheduleAdjustment]) -> str:
        return json.dumps(
            [item.model_dump(mode="json") for item in adjustments],
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def append_adjustment(
        self, run_id: str, adjustment: ScheduleAdjustment
    ) -> tuple[ScheduleAdjustment, ...]:
        """Acrescenta um ajuste à lista da run, renumerando `sequence` no servidor.

        O `sequence` que vier em `adjustment` é descartado: quem numera é o
        store, com `len(atual) + 1`. É essa renumeração que garante que
        `apply_adjustments` (tarefa 3) nunca veja sequência duplicada — o
        empate que ele rejeita não chega a existir aqui.
        """

        with self._connect() as connection:
            row = connection.execute(
                "SELECT adjustments_json FROM pilot_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"run not found: {run_id}")
            current = self._load_adjustments(row)
            appended = adjustment.model_copy(update={"sequence": len(current) + 1})
            updated = (*current, appended)
            connection.execute(
                "UPDATE pilot_runs SET adjustments_json = ? WHERE run_id = ?",
                (self._dump_adjustments(updated), run_id),
            )
        return updated

    def pop_last_adjustment(self, run_id: str) -> tuple[ScheduleAdjustment, ...]:
        """Remove o ajuste de maior `sequence`, não o último da ordem física da lista.

        As duas coisas coincidem no fluxo normal — `append_adjustment` sempre
        numera e acrescenta ao fim —, mas o contrato aqui é sobre `sequence`,
        por isso ordenar antes de descartar em vez de confiar na posição do
        array.
        """

        with self._connect() as connection:
            row = connection.execute(
                "SELECT adjustments_json FROM pilot_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"run not found: {run_id}")
            current = self._load_adjustments(row)
            if not current:
                raise ValueError("run has no adjustment to remove")
            remaining = tuple(sorted(current, key=lambda item: item.sequence)[:-1])
            connection.execute(
                "UPDATE pilot_runs SET adjustments_json = ? WHERE run_id = ?",
                (self._dump_adjustments(remaining), run_id),
            )
        return remaining

    def list_adjustments(self, run_id: str) -> tuple[ScheduleAdjustment, ...]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT adjustments_json FROM pilot_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"run not found: {run_id}")
        return tuple(self._load_adjustments(row))

    def save_constraints(self, run_id: str, constraints: PlanningConstraints) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE pilot_runs SET constraints_json = ? WHERE run_id = ?",
                (constraints.model_dump_json(), run_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"run not found: {run_id}")

    def get_constraints(self, run_id: str) -> PlanningConstraints:
        """Devolve as restrições da run, ou vazias se ela nunca teve nenhuma."""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT constraints_json FROM pilot_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"run not found: {run_id}")
        constraints_json = row["constraints_json"]
        if constraints_json is None:
            return PlanningConstraints()
        return PlanningConstraints.model_validate_json(str(constraints_json))

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> PilotRun:
        summary_json = row["summary_json"]
        decision_json = row["decision_json"]
        trace_payload = json.loads(str(row["trace_json"]))
        artifact_names = tuple(json.loads(str(row["artifact_names_json"])))
        return PilotRun(
            run_id=str(row["run_id"]),
            snapshot_id=str(row["snapshot_id"]),
            tenant_id=str(row["tenant_id"]),
            status=str(row["status"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            started_at=(
                datetime.fromisoformat(str(row["started_at"]))
                if row["started_at"] is not None
                else None
            ),
            completed_at=(
                datetime.fromisoformat(str(row["completed_at"]))
                if row["completed_at"] is not None
                else None
            ),
            request=PlanningRequest.model_validate_json(str(row["request_json"])),
            config=PlanningConfig.model_validate_json(str(row["config_json"])),
            proposal_id=(str(row["proposal_id"]) if row["proposal_id"] is not None else None),
            summary=(
                RunSummary.model_validate_json(str(summary_json))
                if summary_json is not None
                else None
            ),
            error=str(row["error"]) if row["error"] is not None else None,
            current_stage=(
                str(row["current_stage"]) if row["current_stage"] is not None else None
            ),
            trace_events=tuple(
                PlanningStageTrace.model_validate(item) for item in trace_payload
            ),
            artifact_names=artifact_names,
            decision=(
                HumanDecision.model_validate_json(str(decision_json))
                if decision_json is not None
                else None
            ),
        )
