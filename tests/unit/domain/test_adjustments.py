from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from domain.planning.adjustments import AdjustmentKind, ScheduleAdjustment
from domain.planning.enums import UnscheduledReason


def _ajuste(**overrides: object) -> ScheduleAdjustment:
    base: dict[str, object] = {
        "sequence": 1,
        "kind": AdjustmentKind.MOVE,
        "operation_id": "op-1",
        "target_date": date(2026, 8, 19),
        "target_worker_id": "w-1",
        "applied_by": "ana",
        "applied_at": datetime(2026, 8, 19, 12, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return ScheduleAdjustment(**base)


def test_manual_is_an_unscheduled_reason() -> None:
    assert UnscheduledReason.MANUAL.value == "manual"


def test_move_requires_a_destination() -> None:
    with pytest.raises(ValidationError):
        _ajuste(target_worker_id=None)
    with pytest.raises(ValidationError):
        _ajuste(target_date=None)


def test_remove_refuses_a_destination() -> None:
    with pytest.raises(ValidationError):
        _ajuste(kind=AdjustmentKind.REMOVE)


def test_remove_needs_no_destination() -> None:
    ajuste = _ajuste(kind=AdjustmentKind.REMOVE, target_date=None, target_worker_id=None)
    assert ajuste.kind is AdjustmentKind.REMOVE


def test_applied_at_must_carry_a_timezone() -> None:
    with pytest.raises(ValidationError):
        _ajuste(applied_at=datetime(2026, 8, 19, 12, 0))


def test_sequence_starts_at_one() -> None:
    with pytest.raises(ValidationError):
        _ajuste(sequence=0)


def test_applied_at_must_carry_a_timezone_even_on_remove() -> None:
    with pytest.raises(ValidationError):
        _ajuste(
            kind=AdjustmentKind.REMOVE,
            target_date=None,
            target_worker_id=None,
            applied_at=datetime(2026, 8, 19, 12, 0),
        )


def test_applied_at_must_carry_a_timezone_even_on_include() -> None:
    with pytest.raises(ValidationError):
        _ajuste(kind=AdjustmentKind.INCLUDE, applied_at=datetime(2026, 8, 19, 12, 0))


def test_include_with_a_destination_is_valid() -> None:
    ajuste = _ajuste(kind=AdjustmentKind.INCLUDE)
    assert ajuste.kind is AdjustmentKind.INCLUDE
