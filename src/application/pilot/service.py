"""Camada de serviço do piloto: orquestra catálogo, execução e persistência."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

from agent.programmer.coordinator import ProgrammerAgent
from application.config import derive_weights_version
from application.pilot.coverage import capacity_coverage
from application.pilot.exports import export_bundle, json_export, run_summary
from application.pilot.golden_set import golden_set_jsonl
from application.pilot.models import (
    ExportBundle,
    ExportFormat,
    FeedbackInput,
    FeedbackRecord,
    PilotRun,
    RunStatus,
    SnapshotSummary,
)
from application.pilot.store import SnapshotCatalog, SQLitePilotStore
from application.workflows.decide_proposal import decide_proposal
from domain.planning.adjustments import (
    AdjustmentKind,
    PlanningConstraints,
    ScheduleAdjustment,
    apply_adjustments,
)
from domain.planning.config import PlanningConfig
from domain.planning.entities import (
    HumanDecision,
    PlanningRequest,
    PlanningRunResult,
    PlanningSnapshot,
    PlanningStageTrace,
    VerificationViolation,
)
from domain.planning.enums import DecisionType
from domain.planning.verifier import verify_schedule


class RunExecutor(Protocol):
    def submit(self, run_id: str, task: Callable[[], None]) -> None: ...


class PlanningAgent(Protocol):
    """Contrato mínimo consumido pelo serviço, honrado por ``ProgrammerAgent``."""

    async def propose(
        self,
        request: PlanningRequest,
        snapshot: PlanningSnapshot,
        *,
        stage_listener: Callable[[PlanningStageTrace], None] | None = None,
    ) -> PlanningRunResult: ...


class ThreadRunExecutor:
    """Executa um run por vez fora do ciclo de renderização do Streamlit."""

    def __init__(self, max_workers: int = 1) -> None:
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="pilot-run",
        )

    def submit(self, run_id: str, task: Callable[[], None]) -> None:
        self._pool.submit(task)


def _json_text(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
        default=str,
    ) + "\n"


def _sanitized_error(error: BaseException) -> str:
    """Registra o tipo da falha sem propagar dados operacionais."""

    return f"execução interrompida por {type(error).__name__}"


class PilotService:
    """Fachada em processo consumida diretamente pela interface Streamlit."""

    def __init__(
        self,
        *,
        snapshot_dir: Path,
        run_dir: Path,
        db_path: Path,
        executor: RunExecutor | None = None,
        agent: PlanningAgent | None = None,
    ) -> None:
        self._catalog = SnapshotCatalog(snapshot_dir)
        self._run_dir = run_dir
        self._run_dir.mkdir(parents=True, exist_ok=True)
        self._store = SQLitePilotStore(db_path)
        self._store.initialize()
        self._store.recover_interrupted(datetime.now(UTC))
        self._executor = executor or ThreadRunExecutor()
        self._agent = agent

    def list_snapshots(self) -> tuple[SnapshotSummary, ...]:
        return self._catalog.list()

    def start_run(
        self,
        *,
        snapshot_id: str,
        request: PlanningRequest,
        config: PlanningConfig | None = None,
    ) -> PilotRun:
        snapshot = self._catalog.get(snapshot_id)
        effective_config = config or PlanningConfig()
        bound_request = request.model_copy(
            update={"weights_version": derive_weights_version(effective_config)}
        )
        run = PilotRun(
            run_id=str(uuid.uuid4()),
            snapshot_id=snapshot.snapshot_id,
            tenant_id=snapshot.tenant_id,
            status=RunStatus.QUEUED,
            created_at=datetime.now(UTC),
            request=bound_request,
            config=effective_config,
        )
        self._store.create_run(run)
        self._executor.submit(run.run_id, lambda: self._execute(run.run_id))
        return run

    def get_run(self, run_id: str) -> PilotRun:
        run = self._store.get_run(run_id)
        if run is None:
            raise KeyError(f"run not found: {run_id}")
        return run

    def _result(self, run_id: str) -> PlanningRunResult:
        run = self.get_run(run_id)
        if run.status is not RunStatus.COMPLETED:
            raise ValueError("run has no artifacts to query yet")
        path = self._run_dir / run_id / "result.json"
        if not path.is_file():
            raise ValueError("run artifacts are missing from the pilot directory")
        return PlanningRunResult.model_validate_json(path.read_text(encoding="utf-8"))

    def get_backlog(self, run_id: str) -> dict[str, Any]:
        result = self._result(run_id)
        scheduled = {
            assignment.operation_id
            for assignment in result.proposal.solution.assignments
        }
        return {
            "run_id": run_id,
            "backlog": [
                {
                    **item.model_dump(mode="json"),
                    "scheduled": item.operation.operation_id in scheduled,
                }
                for item in result.enriched
            ],
            "capacities": [item.model_dump(mode="json") for item in result.capacities],
        }

    def get_schedule(self, run_id: str) -> dict[str, Any]:
        result = self._result(run_id)
        solution = result.proposal.solution
        return {
            "run_id": run_id,
            "status": solution.status.value,
            "algorithm_version": solution.algorithm_version,
            "objective_value": solution.objective_value,
            "period": result.proposal.period.model_dump(mode="json"),
            "assignments": [item.model_dump(mode="json") for item in solution.assignments],
            "unscheduled": [item.model_dump(mode="json") for item in solution.unscheduled],
            "coverage": capacity_coverage(result).model_dump(mode="json"),
        }

    def get_verification(self, run_id: str) -> dict[str, Any]:
        result = self._result(run_id)
        return {
            "run_id": run_id,
            "proposal_id": result.proposal.proposal_id,
            **result.proposal.verification.model_dump(mode="json"),
        }

    def get_revision(self, run_id: str) -> dict[str, Any]:
        return self._revisao(run_id)

    def add_adjustment(
        self,
        run_id: str,
        *,
        kind: AdjustmentKind,
        operation_id: str,
        target_date: date | None,
        target_worker_id: str | None,
        reason: str | None,
        applied_by: str,
    ) -> dict[str, Any]:
        adjustment = ScheduleAdjustment(
            # `sequence` é descartado por `append_adjustment`, que renumera com
            # `len(atual) + 1`; qualquer valor >= 1 satisfaz a validação aqui.
            sequence=1,
            kind=kind,
            operation_id=operation_id,
            target_date=target_date,
            target_worker_id=target_worker_id,
            reason=reason,
            applied_by=applied_by,
            applied_at=datetime.now(UTC),
        )
        self._store.append_adjustment(run_id, adjustment)
        return self._revisao(run_id)

    def undo_last_adjustment(self, run_id: str) -> dict[str, Any]:
        self._store.pop_last_adjustment(run_id)
        return self._revisao(run_id)

    def set_constraints(self, run_id: str, constraints: PlanningConstraints) -> PlanningConstraints:
        self._store.save_constraints(run_id, constraints)
        return self._store.get_constraints(run_id)

    def _revisao(self, run_id: str) -> dict[str, Any]:
        """Recalcula a semana corrente: proposta original + ajustes, na hora.

        A proposta do agente é imutável; nunca guardamos a solução ajustada,
        porque ela e a lista de ajustes poderiam divergir. O estado corrente é
        sempre `apply_adjustments(proposta_original, ajustes)`, refeito aqui a
        cada chamada, e conferido pelo mesmo `verify_schedule` que confere o
        agente — rodar a verificação sobre a proposta original em vez da
        ajustada é o defeito que esta função existe para não ter.

        Violação criada é a que aparece na verificação da revisão e não
        aparecia na verificação da proposta original, comparando por
        `(code, operation_id)`; o resto é herdada. A comparação usa `Counter`
        para não depender da ordem das duas listas nem contar uma violação
        repetida como criada só porque a original tinha uma cópia a menos.
        """

        run = self.get_run(run_id)
        result = self._result(run_id)
        adjustments = self._store.list_adjustments(run_id)
        snapshot = self._catalog.get(run.snapshot_id)

        adjusted_solution = apply_adjustments(
            result.proposal.solution,
            adjustments,
            snapshot,
            result.enriched,
            run.request,
        )
        original_verification = verify_schedule(
            result.proposal.solution, snapshot, result.enriched, run.request
        )
        revision_verification = verify_schedule(
            adjusted_solution, snapshot, result.enriched, run.request
        )

        pending_original = Counter(
            (violation.code, violation.operation_id)
            for violation in original_verification.violations
        )
        created_violations: list[VerificationViolation] = []
        inherited_violations: list[VerificationViolation] = []
        for violation in revision_verification.violations:
            key = (violation.code, violation.operation_id)
            if pending_original[key] > 0:
                pending_original[key] -= 1
                inherited_violations.append(violation)
            else:
                created_violations.append(violation)

        return {
            "run_id": run_id,
            "revision_sequence": len(adjustments),
            "adjustments": [item.model_dump(mode="json") for item in adjustments],
            "solution": adjusted_solution.model_dump(mode="json"),
            "verification": revision_verification.model_dump(mode="json"),
            "created_violations": [item.model_dump(mode="json") for item in created_violations],
            "inherited_violations": [
                item.model_dump(mode="json") for item in inherited_violations
            ],
        }

    def list_runs(self) -> tuple[PilotRun, ...]:
        return self._store.list_runs()

    def record_decision(
        self,
        *,
        run_id: str,
        decision: DecisionType,
        decided_by: str,
        reason: str,
        decided_at: datetime | None = None,
    ) -> PilotRun:
        run = self.get_run(run_id)
        if run.status is not RunStatus.COMPLETED or run.proposal_id is None:
            raise ValueError("only a completed run can receive a human decision")
        result = self._result(run_id)
        human_decision = HumanDecision(
            proposal_id=run.proposal_id,
            decision=decision,
            decided_by=decided_by,
            decided_at=decided_at or datetime.now(UTC),
            reason=reason,
        )
        reviewed = decide_proposal(result.proposal, human_decision)
        summary = (run.summary or run_summary(result)).model_copy(
            update={"proposal_status": reviewed.status.value}
        )
        updated = self._store.save_decision(run_id, human_decision, summary)
        self._write_artifact(
            run_id,
            "proposal-reviewed.json",
            _json_text(reviewed.model_dump(mode="json")),
        )
        return updated

    def record_feedback(
        self,
        *,
        run_id: str,
        items: Sequence[FeedbackInput],
        recorded_by: str,
        recorded_at: datetime | None = None,
    ) -> tuple[FeedbackRecord, ...]:
        run = self.get_run(run_id)
        moment = recorded_at or datetime.now(UTC)
        records = tuple(
            FeedbackRecord(
                feedback_id=str(uuid.uuid4()),
                run_id=run_id,
                snapshot_id=run.snapshot_id,
                operation_id=item.operation_id,
                skill=item.skill,
                verdict=item.verdict,
                reason=item.reason,
                recorded_by=recorded_by,
                recorded_at=moment,
            )
            for item in items
        )
        self._store.add_feedback(records)
        return records

    def list_feedback(self, run_id: str | None = None) -> tuple[FeedbackRecord, ...]:
        return self._store.list_feedback(run_id)

    def export_golden_set(self, target: Path, run_id: str | None = None) -> int:
        """Grava o feedback coletado no formato consumido pela avaliação offline."""

        records = self._store.list_feedback(run_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(golden_set_jsonl(records), encoding="utf-8")
        temporary.replace(target)
        return len(records)

    def export_run(self, *, run_id: str, format: ExportFormat) -> ExportBundle:
        return export_bundle(self.get_run(run_id), self._result(run_id), format)

    def _execute(self, run_id: str) -> None:
        run = self.get_run(run_id)
        self._store.mark_running(run_id, datetime.now(UTC))
        try:
            snapshot = self._catalog.get(run.snapshot_id)
            agent = self._agent or ProgrammerAgent(run.config)

            def on_stage(event: PlanningStageTrace) -> None:
                self._store.update_progress(run_id, event)

            result = asyncio.run(
                agent.propose(run.request, snapshot, stage_listener=on_stage)
            )
        except BaseException as error:  # noqa: BLE001 - falha segura e registrada
            self._store.mark_failed(
                run_id,
                completed_at=datetime.now(UTC),
                error=_sanitized_error(error),
            )
            return
        summary = run_summary(result)
        artifact_names = self._write_artifacts(run_id, run, result)
        self._store.mark_completed(
            run_id,
            completed_at=datetime.now(UTC),
            proposal_id=result.proposal.proposal_id,
            summary=summary,
            trace_events=result.trace_events,
            artifact_names=artifact_names,
        )

    def _run_directory(self, run_id: str) -> Path:
        directory = self._run_dir / run_id
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _write_artifact(self, run_id: str, name: str, content: str) -> None:
        target = self._run_directory(run_id) / name
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)

    def _write_artifacts(
        self,
        run_id: str,
        run: PilotRun,
        result: PlanningRunResult,
    ) -> tuple[str, ...]:
        bundle = json_export(run, result)
        for name, content in bundle.files.items():
            self._write_artifact(run_id, name, content)
        return tuple(sorted(bundle.files))


__all__ = ["PilotService", "PlanningAgent", "RunExecutor", "ThreadRunExecutor"]
