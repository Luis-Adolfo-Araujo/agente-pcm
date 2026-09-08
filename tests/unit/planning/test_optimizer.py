from datetime import UTC, datetime

from domain.planning.config import OptimizerConfig
from domain.planning.entities import (
    CapacityAssessment,
    CapacitySlot,
    DurationEstimate,
    EnrichedOperation,
    ExecutorCandidate,
    MaterialAssessment,
    PlanningRequest,
    PriorityAssessment,
    TimeWindow,
    WorkOrderOperation,
)
from domain.planning.enums import (
    DurationSource,
    MaterialStatus,
    SolutionStatus,
    UnscheduledReason,
)
from domain.planning.optimizer import optimize_schedule


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, 2, hour, minute, tzinfo=UTC)


def _request() -> PlanningRequest:
    return PlanningRequest(
        tenant_id="planta-modelo",
        period=TimeWindow(start=_dt(8), end=_dt(12)),
        as_of=_dt(7),
    )


def _capacity(worker_id: str, end_hour: int = 10) -> CapacityAssessment:
    window = TimeWindow(start=_dt(8), end=_dt(end_hour))
    return CapacityAssessment(
        worker_id=worker_id,
        gross_minutes=window.minutes,
        committed_minutes=0,
        net_minutes=window.minutes,
        slots=(CapacitySlot(worker_id=worker_id, window=window),),
    )


def _enriched(
    operation_id: str,
    score: float,
    duration: int,
    candidates: tuple[tuple[str, float], ...] = (("worker-a", 80),),
    *,
    required_worker_count: int = 1,
    operational_windows: tuple[TimeWindow, ...] = (),
    material_blocking: bool = False,
) -> EnrichedOperation:
    operation = WorkOrderOperation(
        work_order_id=f"wo-{operation_id}",
        operation_id=operation_id,
        status="open",
        created_at=datetime(2026, 6, 1, 8, tzinfo=UTC),
        required_worker_count=required_worker_count,
        operational_windows=operational_windows,
    )
    return EnrichedOperation(
        operation=operation,
        priority=PriorityAssessment(
            operation_id=operation_id,
            score=score,
            band="high",
            model="A",
            components=(),
            reason_codes=("SLA",),
        ),
        duration=DurationEstimate(
            operation_id=operation_id,
            minutes=duration,
            p50_minutes=duration,
            p80_minutes=duration,
            source=DurationSource.PLANNED,
            sample_size=1,
            confidence=1,
            reason_codes=("PLANNED_DURATION",),
        ),
        materials=MaterialAssessment(
            operation_id=operation_id,
            status=(
                MaterialStatus.UNAVAILABLE
                if material_blocking
                else MaterialStatus.NOT_REQUIRED
            ),
            blocking=material_blocking,
            reason_codes=("MATERIAL_MISSING",) if material_blocking else ("NOT_REQUIRED",),
        ),
        executants=tuple(
            ExecutorCandidate(
                operation_id=operation_id,
                worker_id=worker_id,
                score=candidate_score,
                eligible=True,
                available_minutes=240,
                reason_codes=("ELIGIBLE",),
            )
            for worker_id, candidate_score in candidates
        ),
    )


def test_greedy_optimizer_preserves_priority_and_is_deterministic() -> None:
    high = _enriched("high", 95, 90)
    low = _enriched("low", 40, 60)
    capacity = _capacity("worker-a")

    first = optimize_schedule(
        (low, high),
        (capacity,),
        _request(),
        OptimizerConfig(slot_granularity_minutes=15),
    )
    second = optimize_schedule(
        (high, low),
        {"worker-a": capacity},
        _request(),
        OptimizerConfig(slot_granularity_minutes=15),
    )

    assert first == second
    assert first.status == SolutionStatus.PARTIAL
    assert [assignment.operation_id for assignment in first.assignments] == ["high"]
    assert first.assignments[0].window == TimeWindow(start=_dt(8), end=_dt(9, 30))
    assert first.objective_value == 95
    assert first.unscheduled[0].operation_id == "low"
    assert first.unscheduled[0].reason == UnscheduledReason.NO_CAPACITY


def test_optimizer_finds_a_shared_slot_for_multiple_executants() -> None:
    item = _enriched(
        "multi",
        80,
        60,
        (("worker-c", 50), ("worker-b", 90), ("worker-a", 100)),
        required_worker_count=2,
        operational_windows=(TimeWindow(start=_dt(8, 7), end=_dt(10)),),
    )

    solution = optimize_schedule(
        (item,),
        (_capacity("worker-c", 11), _capacity("worker-b", 11), _capacity("worker-a", 11)),
        _request(),
        OptimizerConfig(slot_granularity_minutes=15),
    )

    assert solution.status == SolutionStatus.FEASIBLE
    assert solution.unscheduled == ()
    assert solution.assignments[0].worker_ids == ("worker-a", "worker-b")
    assert solution.assignments[0].window == TimeWindow(start=_dt(8, 15), end=_dt(9, 15))
    assert "MULTIPLE_EXECUTANTS" in solution.assignments[0].reason_codes


def test_optimizer_keeps_material_blockers_visible_as_unscheduled() -> None:
    blocked = _enriched("blocked", 100, 60, material_blocking=True)

    solution = optimize_schedule(
        (blocked,),
        (_capacity("worker-a"),),
        _request(),
        OptimizerConfig(),
    )

    assert solution.status == SolutionStatus.INFEASIBLE
    assert solution.assignments == ()
    assert solution.unscheduled[0].reason == UnscheduledReason.MATERIAL
    assert solution.unscheduled[0].details == ("MATERIAL_MISSING",)
