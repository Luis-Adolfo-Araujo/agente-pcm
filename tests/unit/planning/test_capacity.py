from datetime import UTC, datetime

from domain.planning.capacity import calculate_capacity
from domain.planning.entities import (
    AvailabilitySlot,
    ExistingAssignment,
    TimeWindow,
    WorkerProfile,
)


def window(start_hour: int, end_hour: int) -> TimeWindow:
    return TimeWindow(
        start=datetime(2026, 8, 17, start_hour, tzinfo=UTC),
        end=datetime(2026, 8, 17, end_hour, tzinfo=UTC),
    )


PERIOD = window(8, 18)


def test_subtracts_commitments_and_returns_remaining_slots() -> None:
    result = calculate_capacity(
        workers=(WorkerProfile(worker_id="worker-1"),),
        availability=(AvailabilitySlot(worker_id="worker-1", window=window(8, 17)),),
        existing_assignments=(
            ExistingAssignment(
                operation_id="op-1", worker_id="worker-1", window=window(10, 12)
            ),
        ),
        period=PERIOD,
    )

    assert len(result) == 1
    capacity = result[0]
    assert capacity.gross_minutes == 9 * 60
    assert capacity.committed_minutes == 2 * 60
    assert capacity.net_minutes == 7 * 60
    assert [slot.window for slot in capacity.slots] == [window(8, 10), window(12, 17)]


def test_merges_overlaps_and_never_counts_commitments_twice() -> None:
    result = calculate_capacity(
        workers=(WorkerProfile(worker_id="worker-1"),),
        availability=(
            AvailabilitySlot(worker_id="worker-1", window=window(8, 13)),
            AvailabilitySlot(worker_id="worker-1", window=window(12, 17)),
        ),
        existing_assignments=(
            ExistingAssignment(
                operation_id="op-1", worker_id="worker-1", window=window(9, 14)
            ),
            ExistingAssignment(
                operation_id="op-2", worker_id="worker-1", window=window(11, 16)
            ),
        ),
        period=PERIOD,
    )[0]

    assert result.gross_minutes == 9 * 60
    assert result.committed_minutes == 7 * 60
    assert result.net_minutes == 2 * 60
    assert [slot.window for slot in result.slots] == [window(8, 9), window(16, 17)]


def test_assignment_outside_availability_does_not_make_capacity_negative() -> None:
    result = calculate_capacity(
        workers=(WorkerProfile(worker_id="worker-1"),),
        availability=(AvailabilitySlot(worker_id="worker-1", window=window(10, 12)),),
        existing_assignments=(
            ExistingAssignment(
                operation_id="all-day", worker_id="worker-1", window=window(8, 18)
            ),
        ),
        period=PERIOD,
    )[0]

    assert result.gross_minutes == 120
    assert result.committed_minutes == 120
    assert result.net_minutes == 0
    assert result.slots == ()


def test_clips_availability_to_period_and_includes_active_worker_without_slots() -> None:
    result = calculate_capacity(
        workers=(
            WorkerProfile(worker_id="worker-b"),
            WorkerProfile(worker_id="worker-a"),
            WorkerProfile(worker_id="inactive", active=False),
        ),
        availability=(
            AvailabilitySlot(worker_id="worker-a", window=window(8, 18)),
            AvailabilitySlot(worker_id="inactive", window=window(8, 18)),
        ),
        existing_assignments=(),
        period=window(10, 12),
    )

    assert [capacity.worker_id for capacity in result] == ["worker-a", "worker-b"]
    assert result[0].gross_minutes == 120
    assert result[0].slots[0].window == window(10, 12)
    assert result[1].gross_minutes == 0
    assert result[1].net_minutes == 0
    assert result[1].slots == ()
