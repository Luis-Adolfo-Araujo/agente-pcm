from datetime import UTC, date, datetime

import pytest

from domain.planning.adjustments import AdjustmentKind, ScheduleAdjustment, apply_adjustments
from domain.planning.enums import UnscheduledReason
from tests.support.planning import enriched_base, request_base, snapshot_base, solution_base


def _adjustment(
    sequence: int,
    kind: AdjustmentKind,
    operation_id: str,
    day: date | None = None,
    worker_id: str | None = None,
) -> ScheduleAdjustment:
    return ScheduleAdjustment(
        sequence=sequence,
        kind=kind,
        operation_id=operation_id,
        target_date=day,
        target_worker_id=worker_id,
        applied_by="ana",
        applied_at=datetime(2026, 8, 19, 12, tzinfo=UTC),
    )


def test_move_changes_worker_and_day() -> None:
    result = apply_adjustments(
        solution_base(),
        [_adjustment(1, AdjustmentKind.MOVE, "op-high", date(2026, 8, 20), "w-2")],
        snapshot_base(),
        enriched_base(),
        request_base(),
    )
    scheduled = next(a for a in result.assignments if a.operation_id == "op-high")
    assert scheduled.worker_ids == ("w-2",)
    assert scheduled.window.start.date() == date(2026, 8, 20)
    assert "MANUAL_ADJUSTMENT" in scheduled.reason_codes


def test_remove_sends_the_order_back_with_a_manual_reason() -> None:
    result = apply_adjustments(
        solution_base(),
        [_adjustment(1, AdjustmentKind.REMOVE, "op-high")],
        snapshot_base(),
        enriched_base(),
        request_base(),
    )
    assert all(a.operation_id != "op-high" for a in result.assignments)
    removed = next(u for u in result.unscheduled if u.operation_id == "op-high")
    assert removed.reason is UnscheduledReason.MANUAL
    assert removed.details == ("MANUAL_REMOVAL",)


def test_include_brings_an_unscheduled_order_in() -> None:
    result = apply_adjustments(
        solution_base(),
        [_adjustment(1, AdjustmentKind.INCLUDE, "op-out", date(2026, 8, 19), "w-1")],
        snapshot_base(),
        enriched_base(),
        request_base(),
    )
    assert any(a.operation_id == "op-out" for a in result.assignments)
    assert all(u.operation_id != "op-out" for u in result.unscheduled)


def test_replay_is_deterministic() -> None:
    adjustments = [
        _adjustment(1, AdjustmentKind.REMOVE, "op-high"),
        _adjustment(2, AdjustmentKind.INCLUDE, "op-out", date(2026, 8, 19), "w-1"),
    ]
    first = apply_adjustments(
        solution_base(), adjustments, snapshot_base(), enriched_base(), request_base()
    )
    second = apply_adjustments(
        solution_base(),
        list(reversed(adjustments)),
        snapshot_base(),
        enriched_base(),
        request_base(),
    )
    assert first == second


def test_moving_an_unscheduled_order_is_refused() -> None:
    with pytest.raises(ValueError, match="not scheduled"):
        apply_adjustments(
            solution_base(),
            [_adjustment(1, AdjustmentKind.MOVE, "op-out", date(2026, 8, 19), "w-1")],
            snapshot_base(),
            enriched_base(),
            request_base(),
        )


def test_including_a_scheduled_order_is_refused() -> None:
    with pytest.raises(ValueError, match="already scheduled"):
        apply_adjustments(
            solution_base(),
            [_adjustment(1, AdjustmentKind.INCLUDE, "op-high", date(2026, 8, 19), "w-1")],
            snapshot_base(),
            enriched_base(),
            request_base(),
        )


def test_duplicate_sequence_is_refused() -> None:
    with pytest.raises(ValueError, match="duplicate sequence"):
        apply_adjustments(
            solution_base(),
            [
                _adjustment(1, AdjustmentKind.MOVE, "op-high", date(2026, 8, 20), "w-2"),
                _adjustment(1, AdjustmentKind.MOVE, "op-medium", date(2026, 8, 20), "w-2"),
            ],
            snapshot_base(),
            enriched_base(),
            request_base(),
        )


def test_two_moves_to_the_same_worker_and_day_do_not_overlap() -> None:
    result = apply_adjustments(
        solution_base(),
        [
            _adjustment(1, AdjustmentKind.MOVE, "op-high", date(2026, 8, 20), "w-2"),
            _adjustment(2, AdjustmentKind.MOVE, "op-medium", date(2026, 8, 20), "w-2"),
        ],
        snapshot_base(),
        enriched_base(),
        request_base(),
    )
    first = next(a for a in result.assignments if a.operation_id == "op-high")
    second = next(a for a in result.assignments if a.operation_id == "op-medium")
    assert second.window.start >= first.window.end

