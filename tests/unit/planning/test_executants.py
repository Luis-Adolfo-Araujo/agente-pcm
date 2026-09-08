from datetime import UTC, datetime

from domain.planning.config import ExecutantConfig
from domain.planning.entities import (
    CapacityAssessment,
    CapacitySlot,
    DurationEstimate,
    HistoricalExecution,
    TimeWindow,
    WorkerProfile,
    WorkOrderOperation,
)
from domain.planning.enums import DurationSource
from domain.planning.executants import suggest_executants


def _dt(day: int, hour: int) -> datetime:
    return datetime(2026, 6, day, hour, tzinfo=UTC)


def _operation() -> WorkOrderOperation:
    return WorkOrderOperation(
        work_order_id="wo-1",
        operation_id="op-1",
        title="Trocar rolamento",
        status="open",
        created_at=_dt(1, 7),
        asset_id="asset-1",
        location_id="location-1",
        activity_type_id="mechanical",
        planned_team_id="team-1",
    )


def _duration(minutes: int = 60) -> DurationEstimate:
    return DurationEstimate(
        operation_id="op-1",
        minutes=minutes,
        p50_minutes=minutes,
        p80_minutes=minutes,
        source=DurationSource.PLANNED,
        sample_size=1,
        confidence=1,
        reason_codes=("PLANNED_DURATION",),
    )


def _capacity(worker_id: str, start_hour: int = 8, end_hour: int = 10) -> CapacityAssessment:
    window = TimeWindow(start=_dt(2, start_hour), end=_dt(2, end_hour))
    return CapacityAssessment(
        worker_id=worker_id,
        gross_minutes=window.minutes,
        committed_minutes=0,
        net_minutes=window.minutes,
        slots=(CapacitySlot(worker_id=worker_id, window=window),),
    )


def test_suggest_executants_prioritizes_matching_history_without_future_leakage() -> None:
    operation = _operation()
    workers = (
        WorkerProfile(worker_id="worker-b", team_ids=("team-2",)),
        WorkerProfile(worker_id="worker-a", team_ids=("team-1",)),
    )
    history = (
        HistoricalExecution(
            work_order_id="old-1",
            operation_id="old-op-1",
            finished_at=_dt(1, 8),
            duration_minutes=55,
            worker_ids=("worker-a",),
            asset_id="asset-1",
            location_id="location-1",
            activity_type_id="mechanical",
            team_id="team-1",
        ),
        # Este registro seria um match perfeito, mas está no futuro do corte.
        HistoricalExecution(
            work_order_id="future",
            operation_id="future-op",
            finished_at=_dt(3, 8),
            duration_minutes=60,
            worker_ids=("worker-b",),
            asset_id="asset-1",
            location_id="location-1",
            activity_type_id="mechanical",
            team_id="team-1",
        ),
    )

    result = suggest_executants(
        (operation,),
        {"op-1": _duration()},
        (_capacity("worker-b"), _capacity("worker-a")),
        workers,
        history,
        _dt(2, 7),
        ExecutantConfig(),
    )

    candidates = result["op-1"]
    assert [candidate.worker_id for candidate in candidates] == ["worker-a", "worker-b"]
    assert candidates[0].score == 100
    assert candidates[0].eligible is True
    assert "ASSET_EXPERIENCE" in candidates[0].reason_codes
    assert "HISTORICAL_FREQUENCY" not in candidates[1].reason_codes


def test_suggest_executants_requires_a_contiguous_slot_and_is_deterministic() -> None:
    operation = _operation()
    split_capacity = CapacityAssessment(
        worker_id="worker-a",
        gross_minutes=120,
        committed_minutes=0,
        net_minutes=120,
        slots=(
            CapacitySlot(
                worker_id="worker-a",
                window=TimeWindow(start=_dt(2, 8), end=_dt(2, 9)),
            ),
            CapacitySlot(
                worker_id="worker-a",
                window=TimeWindow(start=_dt(2, 10), end=_dt(2, 11)),
            ),
        ),
    )
    estimate = _duration(90)
    workers = (WorkerProfile(worker_id="worker-a", team_ids=("team-1",)),)

    first = suggest_executants(
        (operation,),
        (estimate,),
        (split_capacity,),
        workers,
        (),
        _dt(2, 7),
        ExecutantConfig(),
    )
    second = suggest_executants(
        reversed((operation,)),
        {"op-1": estimate},
        {"worker-a": split_capacity},
        reversed(workers),
        (),
        _dt(2, 7),
        ExecutantConfig(),
    )

    candidate = first["op-1"][0]
    assert first == second
    assert candidate.eligible is False
    assert "NO_CONTIGUOUS_SLOT" in candidate.reason_codes
