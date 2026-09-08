from datetime import UTC, datetime

from domain.planning.entities import (
    AvailabilitySlot,
    DurationEstimate,
    EnrichedOperation,
    ExecutorCandidate,
    MaterialAssessment,
    PlanningRequest,
    PlanningSnapshot,
    PriorityAssessment,
    ScheduleAssignment,
    SchedulingSolution,
    TimeWindow,
    WorkerProfile,
    WorkOrderOperation,
)
from domain.planning.enums import DurationSource, MaterialStatus, SolutionStatus
from domain.planning.verifier import verify_schedule


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, 2, hour, minute, tzinfo=UTC)


def _request() -> PlanningRequest:
    return PlanningRequest(
        tenant_id="planta-modelo",
        period=TimeWindow(start=_dt(8), end=_dt(12)),
        as_of=_dt(7),
    )


def _operation(
    operation_id: str, operational_window: TimeWindow | None = None
) -> WorkOrderOperation:
    return WorkOrderOperation(
        work_order_id=f"wo-{operation_id}",
        operation_id=operation_id,
        status="open",
        created_at=datetime(2026, 6, 1, 8, tzinfo=UTC),
        operational_windows=(operational_window,) if operational_window else (),
    )


def _enriched(
    operation: WorkOrderOperation,
    *,
    material_blocking: bool = False,
    candidate_eligible: bool = True,
) -> EnrichedOperation:
    return EnrichedOperation(
        operation=operation,
        priority=PriorityAssessment(
            operation_id=operation.operation_id,
            score=80,
            band="high",
            model="A",
            components=(),
            reason_codes=("SLA",),
        ),
        duration=DurationEstimate(
            operation_id=operation.operation_id,
            minutes=60,
            p50_minutes=60,
            p80_minutes=60,
            source=DurationSource.PLANNED,
            sample_size=1,
            confidence=1,
            reason_codes=("PLANNED_DURATION",),
        ),
        materials=MaterialAssessment(
            operation_id=operation.operation_id,
            status=(
                MaterialStatus.UNAVAILABLE
                if material_blocking
                else MaterialStatus.NOT_REQUIRED
            ),
            blocking=material_blocking,
            reason_codes=("MATERIAL_MISSING",) if material_blocking else ("NOT_REQUIRED",),
        ),
        executants=(
            ExecutorCandidate(
                operation_id=operation.operation_id,
                worker_id="worker-a",
                score=90,
                eligible=candidate_eligible,
                available_minutes=240,
                reason_codes=("ELIGIBLE",) if candidate_eligible else ("NO_CAPACITY",),
            ),
        ),
    )


def _snapshot(operations: tuple[WorkOrderOperation, ...]) -> PlanningSnapshot:
    return PlanningSnapshot(
        snapshot_id="snapshot-1",
        tenant_id="planta-modelo",
        as_of=_dt(7),
        operations=operations,
        workers=(WorkerProfile(worker_id="worker-a"),),
        availability=(
            AvailabilitySlot(
                worker_id="worker-a",
                window=TimeWindow(start=_dt(8), end=_dt(12)),
            ),
        ),
    )


def _assignment(operation_id: str, start: datetime, end: datetime) -> ScheduleAssignment:
    return ScheduleAssignment(
        work_order_id=f"wo-{operation_id}",
        operation_id=operation_id,
        worker_ids=("worker-a",),
        window=TimeWindow(start=start, end=end),
        priority_score=80,
        reason_codes=("PRIORITY_ORDER",),
    )


def test_verifier_accepts_a_valid_solution_and_hashes_its_inputs() -> None:
    operation = _operation("op-1")
    enriched = (_enriched(operation),)
    solution = SchedulingSolution(
        status=SolutionStatus.FEASIBLE,
        assignments=(_assignment("op-1", _dt(8), _dt(9)),),
        unscheduled=(),
        objective_value=80,
        algorithm_version="greedy-v1",
    )

    first = verify_schedule(solution, _snapshot((operation,)), enriched, _request())
    second = verify_schedule(solution, _snapshot((operation,)), reversed(enriched), _request())

    assert first.valid is True
    assert first.violations == ()
    assert first.input_hash == second.input_hash
    assert len(first.input_hash) == 64


def test_verifier_detects_conflicts_without_reusing_optimizer_logic() -> None:
    operation_a = _operation("op-a")
    operation_b = _operation("op-b", TimeWindow(start=_dt(10), end=_dt(12)))
    enriched = (
        _enriched(operation_a),
        _enriched(operation_b, material_blocking=True, candidate_eligible=False),
    )
    invalid_assignment = _assignment("op-a", _dt(8), _dt(9)).model_copy(
        update={"reason_codes": ()}
    )
    solution = SchedulingSolution(
        status=SolutionStatus.FEASIBLE,
        assignments=(
            invalid_assignment,
            _assignment("op-b", _dt(8, 30), _dt(9, 30)),
        ),
        unscheduled=(),
        objective_value=160,
        algorithm_version="greedy-v1",
    )

    report = verify_schedule(
        solution,
        _snapshot((operation_a, operation_b)),
        enriched,
        _request(),
    )
    codes = {violation.code for violation in report.violations}

    assert report.valid is False
    assert {
        "MISSING_JUSTIFICATION",
        "OUTSIDE_OPERATIONAL_WINDOW",
        "BLOCKING_MATERIAL",
        "INELIGIBLE_EXECUTANT",
        "WORKER_OVERLAP",
    } <= codes
