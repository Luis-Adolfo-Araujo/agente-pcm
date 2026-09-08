from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from application.config import derive_weights_version
from application.pilot.models import (
    ExportFormat,
    FeedbackInput,
    FeedbackSkill,
    FeedbackVerdict,
    RunStatus,
)
from application.pilot.service import PilotService
from application.workflows.generate_schedule import generate_schedule
from domain.planning.config import PlanningConfig
from domain.planning.entities import (
    AvailabilitySlot,
    HistoricalExecution,
    InventoryPosition,
    MaterialRequirement,
    PlanningRequest,
    PlanningRunResult,
    PlanningSnapshot,
    PlanningStageTrace,
    TimeWindow,
    VerificationViolation,
    WorkerProfile,
    WorkOrderOperation,
)
from domain.planning.enums import DecisionType, ProposalStatus, ViolationSeverity
from presentation.view_models import (
    backlog_rows,
    capacity_rows,
    executant_rows,
    schedule_rows,
    unscheduled_rows,
    verification_view,
)

AS_OF = datetime(2026, 8, 17, 12, tzinfo=UTC)
PERIOD = TimeWindow(
    start=datetime(2026, 8, 18, 8, tzinfo=UTC),
    end=datetime(2026, 8, 18, 17, tzinfo=UTC),
)


def _snapshot() -> PlanningSnapshot:
    operations = (
        WorkOrderOperation(
            work_order_id="wo-high",
            operation_id="op-high",
            title="Inspecionar redutor",
            status="open",
            planning_status="unplanned",
            created_at=datetime(2026, 7, 1, tzinfo=UTC),
            due_at=datetime(2026, 8, 16, tzinfo=UTC),
            priority_level=1,
            asset_id="asset-1",
            planned_team_id="mechanical",
            planned_duration_minutes=60,
        ),
        WorkOrderOperation(
            work_order_id="wo-medium",
            operation_id="op-medium",
            title="Trocar rolamento",
            status="open",
            planning_status="without_planning",
            created_at=datetime(2026, 8, 1, tzinfo=UTC),
            due_at=datetime(2026, 8, 25, tzinfo=UTC),
            priority_level=3,
            asset_id="asset-1",
            planned_team_id="mechanical",
            planned_duration_minutes=120,
            required_materials=(MaterialRequirement(item_id="bearing", quantity=1),),
        ),
    )
    return PlanningSnapshot(
        snapshot_id="fixture-1",
        tenant_id="planta-modelo",
        as_of=AS_OF,
        operations=operations,
        inventory=(InventoryPosition(item_id="bearing", on_hand_quantity=2),),
        workers=(
            WorkerProfile(worker_id="worker-1", team_ids=("mechanical",)),
            WorkerProfile(worker_id="worker-2", team_ids=("mechanical",)),
        ),
        availability=(
            AvailabilitySlot(worker_id="worker-1", window=PERIOD),
            AvailabilitySlot(worker_id="worker-2", window=PERIOD),
        ),
        history=(
            HistoricalExecution(
                work_order_id="wo-old",
                operation_id="op-old",
                title="Inspecionar redutor",
                finished_at=datetime(2026, 8, 1, tzinfo=UTC),
                duration_minutes=55,
                worker_ids=("worker-1",),
                asset_id="asset-1",
                team_id="mechanical",
            ),
        ),
    )


class DeferredExecutor:
    """Guarda a tarefa para o teste decidir quando a execução acontece."""

    def __init__(self) -> None:
        self.pending: list[Callable[[], None]] = []

    def submit(self, run_id: str, task: Callable[[], None]) -> None:
        self.pending.append(task)

    def drain(self) -> None:
        while self.pending:
            self.pending.pop(0)()


@pytest.fixture()
def executor() -> DeferredExecutor:
    return DeferredExecutor()


@pytest.fixture()
def service(tmp_path: Path, executor: DeferredExecutor) -> PilotService:
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    (snapshot_dir / "fixture-1.json").write_text(
        _snapshot().model_dump_json(indent=2),
        encoding="utf-8",
    )
    return PilotService(
        snapshot_dir=snapshot_dir,
        run_dir=tmp_path / "runs",
        db_path=tmp_path / "pilot.sqlite3",
        executor=executor,
    )


def _completed_run(service: PilotService, executor: DeferredExecutor) -> str:
    run = service.start_run(snapshot_id="fixture-1", request=_request())
    executor.drain()
    return run.run_id


def _request() -> PlanningRequest:
    return PlanningRequest(tenant_id="planta-modelo", period=PERIOD, as_of=AS_OF)


class InvalidProposalAgent:
    """Reproduz uma proposta reprovada pelo verificador independente."""

    async def propose(
        self,
        request: PlanningRequest,
        snapshot: PlanningSnapshot,
        *,
        stage_listener: Callable[[PlanningStageTrace], None] | None = None,
    ) -> PlanningRunResult:
        result = await generate_schedule(request, snapshot, PlanningConfig())
        verification = result.proposal.verification.model_copy(
            update={
                "valid": False,
                "violations": (
                    VerificationViolation(
                        code="WORKER_DOUBLE_BOOKED",
                        severity=ViolationSeverity.ERROR,
                        details="colisão de agenda injetada pelo teste",
                    ),
                ),
            }
        )
        proposal = result.proposal.model_copy(
            update={"verification": verification, "status": ProposalStatus.INVALID}
        )
        return result.model_copy(update={"proposal": proposal})


@pytest.fixture()
def invalid_service(tmp_path: Path, executor: DeferredExecutor) -> PilotService:
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    (snapshot_dir / "fixture-1.json").write_text(
        _snapshot().model_dump_json(indent=2),
        encoding="utf-8",
    )
    return PilotService(
        snapshot_dir=snapshot_dir,
        run_dir=tmp_path / "runs",
        db_path=tmp_path / "pilot.sqlite3",
        executor=executor,
        agent=InvalidProposalAgent(),
    )


def test_list_snapshots_exposes_frozen_catalog_with_quality(service: PilotService) -> None:
    summaries = service.list_snapshots()

    assert [item.snapshot_id for item in summaries] == ["fixture-1"]
    quality = summaries[0].quality
    assert quality.operation_count == 2
    assert quality.worker_count == 2
    assert {indicator.key for indicator in quality.indicators} >= {
        "operations_with_priority",
        "operations_with_sla",
    }


def test_start_run_queues_the_work_without_executing_it(
    service: PilotService,
    executor: DeferredExecutor,
) -> None:
    run = service.start_run(snapshot_id="fixture-1", request=_request())

    assert run.status is RunStatus.QUEUED
    assert run.snapshot_id == "fixture-1"
    assert run.tenant_id == "planta-modelo"
    assert run.proposal_id is None
    assert len(executor.pending) == 1
    assert service.get_run(run.run_id).status is RunStatus.QUEUED


def test_start_run_binds_weights_version_to_the_configuration_hash(
    service: PilotService,
) -> None:
    config = PlanningConfig()

    run = service.start_run(snapshot_id="fixture-1", request=_request(), config=config)

    assert run.request.weights_version == derive_weights_version(config)


def test_start_run_rejects_a_snapshot_outside_the_catalog(service: PilotService) -> None:
    with pytest.raises(KeyError):
        service.start_run(snapshot_id="does-not-exist", request=_request())


def test_draining_the_executor_completes_the_run_and_persists_artifacts(
    service: PilotService,
    executor: DeferredExecutor,
) -> None:
    run_id = _completed_run(service, executor)

    run = service.get_run(run_id)
    assert run.status is RunStatus.COMPLETED
    assert run.proposal_id is not None
    assert run.summary is not None
    assert run.summary.assignments == 2
    assert run.summary.violations == 0
    assert run.summary.verification_valid is True
    assert [event.stage for event in run.trace_events] == [
        "snapshot_validated",
        "skill.rank_backlog",
        "skill.estimate_duration",
        "skill.check_materials",
        "skill.calculate_capacity",
        "skills_parallel",
        "executant_candidates",
        "optimization",
        "verification",
        "proposal_ready",
    ]
    assert set(run.artifact_names) >= {
        "proposal.json",
        "verification.json",
        "enrichment.json",
        "summary.json",
        "trace.jsonl",
    }


def test_get_backlog_feeds_the_ranking_and_laboratory_views(
    service: PilotService,
    executor: DeferredExecutor,
) -> None:
    run_id = _completed_run(service, executor)

    payload = service.get_backlog(run_id)

    rows = backlog_rows(payload)
    assert [row["operação"] for row in rows] == ["op-high", "op-medium"]
    assert rows[0]["programada"] is True
    assert rows[0]["modelo"] == "model_a"
    assert capacity_rows(payload)
    assert {row["operação"] for row in executant_rows(payload)} == {
        "op-high",
        "op-medium",
    }


def test_get_schedule_feeds_the_week_and_unscheduled_views(
    service: PilotService,
    executor: DeferredExecutor,
) -> None:
    run_id = _completed_run(service, executor)

    payload = service.get_schedule(run_id)

    rows = schedule_rows(payload, service.get_backlog(run_id))
    assert len(rows) == 2
    assert all(row["executantes"] for row in rows)
    assert unscheduled_rows(payload, service.get_backlog(run_id)) == []


def test_get_schedule_reports_capacity_coverage_next_to_the_unscheduled(
    service: PilotService,
    executor: DeferredExecutor,
) -> None:
    run_id = _completed_run(service, executor)

    coverage = service.get_schedule(run_id)["coverage"]

    assert coverage["scheduled_operations"] == 2
    assert coverage["capacity_limited_operations"] == 0
    assert coverage["coverage_percent"] == 100.0


def test_get_verification_reports_the_independent_check(
    service: PilotService,
    executor: DeferredExecutor,
) -> None:
    run_id = _completed_run(service, executor)

    view = verification_view(service.get_verification(run_id))

    assert view["valid"] is True
    assert view["error_count"] == 0
    assert len(view["input_hash"]) == 64


def test_queries_refuse_a_run_without_artifacts(service: PilotService) -> None:
    run = service.start_run(snapshot_id="fixture-1", request=_request())

    with pytest.raises(ValueError):
        service.get_backlog(run.run_id)


def test_record_decision_persists_the_human_gate(
    service: PilotService,
    executor: DeferredExecutor,
) -> None:
    run_id = _completed_run(service, executor)

    updated = service.record_decision(
        run_id=run_id,
        decision=DecisionType.APPROVE,
        decided_by="planejador-1",
        reason="Programação revisada com o PCM",
    )

    assert updated.decision is not None
    assert updated.decision.decision is DecisionType.APPROVE
    assert updated.decision.decided_by == "planejador-1"
    assert updated.decision.proposal_id == updated.proposal_id
    assert service.get_run(run_id).decision is not None


def test_record_decision_refuses_to_approve_an_invalid_proposal(
    invalid_service: PilotService,
    executor: DeferredExecutor,
) -> None:
    run_id = _completed_run(invalid_service, executor)

    with pytest.raises(ValueError):
        invalid_service.record_decision(
            run_id=run_id,
            decision=DecisionType.APPROVE,
            decided_by="planejador-1",
            reason="tentativa indevida",
        )

    assert invalid_service.get_run(run_id).decision is None


def test_record_decision_allows_rejecting_an_invalid_proposal(
    invalid_service: PilotService,
    executor: DeferredExecutor,
) -> None:
    run_id = _completed_run(invalid_service, executor)

    updated = invalid_service.record_decision(
        run_id=run_id,
        decision=DecisionType.REJECT,
        decided_by="coordenador-1",
        reason="violação dura encontrada",
    )

    assert updated.decision is not None
    assert updated.decision.decision is DecisionType.REJECT


def test_record_feedback_keys_every_item_to_the_golden_set(
    service: PilotService,
    executor: DeferredExecutor,
) -> None:
    run_id = _completed_run(service, executor)

    records = service.record_feedback(
        run_id=run_id,
        items=(
            FeedbackInput(
                operation_id="op-high",
                skill=FeedbackSkill.RANKING,
                verdict=FeedbackVerdict.CORRECT,
                reason="prioridade coerente com o SLA vencido",
            ),
            FeedbackInput(
                operation_id="op-medium",
                skill=FeedbackSkill.DURATION,
                verdict=FeedbackVerdict.INCORRECT,
                reason="duração planejada não reflete a troca de rolamento",
            ),
        ),
        recorded_by="planejador-1",
    )

    assert len(records) == 2
    assert {record.snapshot_id for record in records} == {"fixture-1"}
    assert {record.run_id for record in records} == {run_id}
    assert len({record.feedback_id for record in records}) == 2
    assert len(service.list_feedback(run_id)) == 2


def test_export_golden_set_writes_every_evaluation_collected_so_far(
    service: PilotService,
    executor: DeferredExecutor,
    tmp_path: Path,
) -> None:
    run_id = _completed_run(service, executor)
    service.record_feedback(
        run_id=run_id,
        items=(
            FeedbackInput(
                operation_id="op-high",
                skill=FeedbackSkill.RANKING,
                verdict=FeedbackVerdict.CORRECT,
                reason="prioridade coerente",
            ),
        ),
        recorded_by="planejador-1",
    )
    target = tmp_path / "datasets" / "golden-set.jsonl"

    written = service.export_golden_set(target)

    assert written == 1
    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert '"skill":"ranking"' in lines[0]
    assert "planejador-1" not in lines[0]


def test_export_run_produces_the_three_planned_csv_files(
    service: PilotService,
    executor: DeferredExecutor,
) -> None:
    run_id = _completed_run(service, executor)

    bundle = service.export_run(run_id=run_id, format=ExportFormat.CSV)

    assert set(bundle.files) == {"ranking.csv", "schedule.csv", "unscheduled.csv"}
    assert bundle.files["ranking.csv"].splitlines()[0].startswith("position,work_order_id")
    assert len(bundle.files["schedule.csv"].splitlines()) == 3


def test_export_run_produces_the_auditable_json_artifacts(
    service: PilotService,
    executor: DeferredExecutor,
) -> None:
    run_id = _completed_run(service, executor)

    bundle = service.export_run(run_id=run_id, format=ExportFormat.JSON)

    assert {"proposal.json", "verification.json", "enrichment.json"} <= set(bundle.files)


def test_list_runs_returns_the_newest_first(
    service: PilotService,
    executor: DeferredExecutor,
) -> None:
    first = service.start_run(snapshot_id="fixture-1", request=_request())
    second = service.start_run(snapshot_id="fixture-1", request=_request())
    executor.drain()

    identifiers = [run.run_id for run in service.list_runs()]

    assert set(identifiers) == {first.run_id, second.run_id}


def test_restart_marks_abandoned_runs_as_interrupted(
    tmp_path: Path,
    executor: DeferredExecutor,
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    (snapshot_dir / "fixture-1.json").write_text(
        _snapshot().model_dump_json(indent=2),
        encoding="utf-8",
    )
    run_dir = tmp_path / "runs"
    db_path = tmp_path / "pilot.sqlite3"
    first = PilotService(
        snapshot_dir=snapshot_dir,
        run_dir=run_dir,
        db_path=db_path,
        executor=executor,
    )
    abandoned = first.start_run(snapshot_id="fixture-1", request=_request())

    restarted = PilotService(
        snapshot_dir=snapshot_dir,
        run_dir=run_dir,
        db_path=db_path,
        executor=executor,
    )

    run = restarted.get_run(abandoned.run_id)
    assert run.status is RunStatus.INTERRUPTED
    assert run.error
