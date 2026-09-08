from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from application.pilot.models import (
    FeedbackRecord,
    FeedbackSkill,
    FeedbackVerdict,
    PilotRun,
    RunStatus,
    RunSummary,
)
from application.pilot.store import (
    SnapshotCatalog,
    SnapshotCatalogError,
    SnapshotChangedError,
    SQLitePilotStore,
    snapshot_quality,
)
from domain.planning.config import PlanningConfig
from domain.planning.entities import (
    HumanDecision,
    PlanningRequest,
    PlanningSnapshot,
    PlanningStageTrace,
    TimeWindow,
    WorkerProfile,
    WorkOrderOperation,
)
from domain.planning.enums import DecisionType

AS_OF = datetime(2026, 8, 17, 12, tzinfo=UTC)
PERIOD = TimeWindow(
    start=datetime(2026, 8, 18, tzinfo=UTC),
    end=datetime(2026, 8, 25, tzinfo=UTC),
)


def _snapshot(snapshot_id: str = "snap-1") -> PlanningSnapshot:
    return PlanningSnapshot(
        snapshot_id=snapshot_id,
        tenant_id="planta-modelo",
        as_of=AS_OF,
        operations=(
            WorkOrderOperation(
                work_order_id="wo-1",
                operation_id="op-1",
                status="open",
                created_at=datetime(2026, 8, 1, tzinfo=UTC),
                due_at=datetime(2026, 8, 20, tzinfo=UTC),
                priority_level=2,
                asset_id="asset-1",
            ),
            WorkOrderOperation(
                work_order_id="wo-2",
                operation_id="op-2",
                status="open",
                created_at=datetime(2026, 8, 2, tzinfo=UTC),
            ),
        ),
        workers=(WorkerProfile(worker_id="worker-1"),),
        metadata={"source": "tractian", "rejected_records": 3},
    )


def _write(directory: Path, snapshot: PlanningSnapshot, name: str = "snap.json") -> Path:
    path = directory / name
    path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
    return path


def _run(run_id: str = "run-1") -> PilotRun:
    return PilotRun(
        run_id=run_id,
        snapshot_id="snap-1",
        tenant_id="planta-modelo",
        status=RunStatus.QUEUED,
        created_at=AS_OF,
        request=PlanningRequest(tenant_id="planta-modelo", period=PERIOD, as_of=AS_OF),
        config=PlanningConfig(),
    )


def _summary() -> RunSummary:
    return RunSummary(
        proposal_status="draft",
        verification_valid=True,
        assignments=2,
        unscheduled=0,
        violations=0,
        objective_value=10.0,
    )


def _store(tmp_path: Path) -> SQLitePilotStore:
    store = SQLitePilotStore(tmp_path / "pilot.sqlite3")
    store.initialize()
    return store


def test_quality_counts_missing_fields_without_inventing_values() -> None:
    quality = snapshot_quality(_snapshot())

    indicators = {item.key: item for item in quality.indicators}
    assert indicators["operations_with_priority"].present == 1
    assert indicators["operations_with_priority"].missing == 1
    assert indicators["operations_with_sla"].coverage_percent == 50.0
    assert quality.rejected_record_count == 3


def test_catalog_indexes_a_frozen_snapshot_with_its_digest(tmp_path: Path) -> None:
    _write(tmp_path, _snapshot())

    summaries = SnapshotCatalog(tmp_path).list()

    assert [item.snapshot_id for item in summaries] == ["snap-1"]
    assert len(summaries[0].sha256) == 64


def test_catalog_detects_a_snapshot_edited_after_indexing(tmp_path: Path) -> None:
    path = _write(tmp_path, _snapshot())
    catalog = SnapshotCatalog(tmp_path)

    path.write_text(
        _snapshot().model_copy(update={"tenant_id": "outro"}).model_dump_json(indent=2),
        encoding="utf-8",
    )

    with pytest.raises(SnapshotChangedError):
        catalog.get("snap-1")


def test_catalog_refuses_a_symlinked_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "outside"
    source.mkdir()
    real = _write(source, _snapshot())
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir()
    (catalog_dir / "link.json").symlink_to(real)

    with pytest.raises(SnapshotCatalogError):
        SnapshotCatalog(catalog_dir)


def test_catalog_refuses_two_files_with_the_same_snapshot_id(tmp_path: Path) -> None:
    _write(tmp_path, _snapshot(), "a.json")
    _write(tmp_path, _snapshot(), "b.json")

    with pytest.raises(SnapshotCatalogError):
        SnapshotCatalog(tmp_path)


def test_catalog_refuses_a_file_that_is_not_a_canonical_snapshot(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text('{"snapshot_id": "x"}', encoding="utf-8")

    with pytest.raises(SnapshotCatalogError):
        SnapshotCatalog(tmp_path)


def test_catalog_refuses_duplicate_json_keys(tmp_path: Path) -> None:
    (tmp_path / "dup.json").write_text(
        '{"snapshot_id": "a", "snapshot_id": "b"}',
        encoding="utf-8",
    )

    with pytest.raises(SnapshotCatalogError):
        SnapshotCatalog(tmp_path)


def test_run_advances_through_the_expected_states(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_run(_run())

    store.mark_running("run-1", AS_OF)
    store.update_progress(
        "run-1",
        PlanningStageTrace(sequence=1, stage="snapshot_validated", elapsed_ms=1.0),
    )
    completed = store.mark_completed(
        "run-1",
        completed_at=AS_OF,
        proposal_id="proposal-1",
        summary=_summary(),
        trace_events=(
            PlanningStageTrace(sequence=1, stage="snapshot_validated", elapsed_ms=1.0),
        ),
        artifact_names=("proposal.json",),
    )

    assert completed.status is RunStatus.COMPLETED
    assert completed.proposal_id == "proposal-1"
    assert completed.artifact_names == ("proposal.json",)


def test_progress_is_refused_before_the_run_starts(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_run(_run())

    with pytest.raises(ValueError):
        store.update_progress(
            "run-1",
            PlanningStageTrace(sequence=1, stage="snapshot_validated", elapsed_ms=1.0),
        )


def test_progress_requires_an_increasing_sequence(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_run(_run())
    store.mark_running("run-1", AS_OF)
    store.update_progress(
        "run-1",
        PlanningStageTrace(sequence=2, stage="skills_parallel", elapsed_ms=2.0),
    )

    with pytest.raises(ValueError):
        store.update_progress(
            "run-1",
            PlanningStageTrace(sequence=1, stage="snapshot_validated", elapsed_ms=1.0),
        )


def test_a_run_cannot_be_completed_twice(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_run(_run())
    store.mark_running("run-1", AS_OF)
    store.mark_completed(
        "run-1",
        completed_at=AS_OF,
        proposal_id="proposal-1",
        summary=_summary(),
        trace_events=(),
        artifact_names=(),
    )

    with pytest.raises(ValueError):
        store.mark_completed(
            "run-1",
            completed_at=AS_OF,
            proposal_id="proposal-1",
            summary=_summary(),
            trace_events=(),
            artifact_names=(),
        )


def test_recovery_only_touches_runs_that_never_finished(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_run(_run("run-done"))
    store.mark_running("run-done", AS_OF)
    store.mark_completed(
        "run-done",
        completed_at=AS_OF,
        proposal_id="proposal-1",
        summary=_summary(),
        trace_events=(),
        artifact_names=(),
    )
    store.create_run(_run("run-zombie"))

    recovered = store.recover_interrupted(AS_OF)

    assert recovered == 1
    done = store.get_run("run-done")
    zombie = store.get_run("run-zombie")
    assert done is not None and done.status is RunStatus.COMPLETED
    assert zombie is not None and zombie.status is RunStatus.INTERRUPTED


def _completed_store(tmp_path: Path) -> SQLitePilotStore:
    store = _store(tmp_path)
    store.create_run(_run())
    store.mark_running("run-1", AS_OF)
    store.mark_completed(
        "run-1",
        completed_at=AS_OF,
        proposal_id="proposal-1",
        summary=_summary(),
        trace_events=(),
        artifact_names=(),
    )
    return store


def _decision(proposal_id: str = "proposal-1") -> HumanDecision:
    return HumanDecision(
        proposal_id=proposal_id,
        decision=DecisionType.APPROVE,
        decided_by="planejador-1",
        decided_at=AS_OF,
        reason="revisado",
    )


def test_decision_is_stored_once_per_run(tmp_path: Path) -> None:
    store = _completed_store(tmp_path)
    store.save_decision("run-1", _decision(), _summary())

    with pytest.raises(ValueError):
        store.save_decision("run-1", _decision(), _summary())


def test_decision_must_reference_the_run_proposal(tmp_path: Path) -> None:
    store = _completed_store(tmp_path)

    with pytest.raises(ValueError):
        store.save_decision("run-1", _decision("outra-proposta"), _summary())


def test_decision_is_refused_while_the_run_is_not_complete(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_run(_run())

    with pytest.raises(ValueError):
        store.save_decision("run-1", _decision(), _summary())


def test_feedback_round_trips_and_filters_by_run(tmp_path: Path) -> None:
    store = _completed_store(tmp_path)
    store.add_feedback(
        (
            FeedbackRecord(
                feedback_id="f-1",
                run_id="run-1",
                snapshot_id="snap-1",
                operation_id="op-1",
                skill=FeedbackSkill.RANKING,
                verdict=FeedbackVerdict.CORRECT,
                reason="ok",
                recorded_by="planejador-1",
                recorded_at=AS_OF,
            ),
        )
    )

    assert len(store.list_feedback()) == 1
    assert len(store.list_feedback("run-1")) == 1
    assert store.list_feedback("outro-run") == ()
