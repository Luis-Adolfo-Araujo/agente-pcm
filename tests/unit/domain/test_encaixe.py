from datetime import UTC, date, datetime, timedelta

from domain.planning.adjustments import fit_window
from domain.planning.entities import AvailabilitySlot, TimeWindow


def _window(start_hour: int, end_hour: int) -> TimeWindow:
    return TimeWindow(
        start=datetime(2026, 8, 19, start_hour, tzinfo=UTC),
        end=datetime(2026, 8, 19, end_hour, tzinfo=UTC),
    )


def _shift() -> list[AvailabilitySlot]:
    return [AvailabilitySlot(worker_id="w-1", window=_window(8, 16))]


def test_fits_at_the_start_of_an_empty_shift() -> None:
    window = fit_window(
        worker_id="w-1", day=date(2026, 8, 19), minutes=120,
        availability=_shift(), busy=[], slot_minutes=15, tz=UTC,
    )
    assert window.start == datetime(2026, 8, 19, 8, tzinfo=UTC)
    assert window.end == datetime(2026, 8, 19, 10, tzinfo=UTC)


def test_takes_the_first_gap_after_committed_work() -> None:
    window = fit_window(
        worker_id="w-1", day=date(2026, 8, 19), minutes=60,
        availability=_shift(), busy=[_window(8, 11)],
        slot_minutes=15, tz=UTC,
    )
    assert window.start == datetime(2026, 8, 19, 11, tzinfo=UTC)


def test_aligns_to_the_slot_grid() -> None:
    busy_window = TimeWindow(
        start=datetime(2026, 8, 19, 8, tzinfo=UTC),
        end=datetime(2026, 8, 19, 8, 50, tzinfo=UTC),
    )
    window = fit_window(
        worker_id="w-1", day=date(2026, 8, 19), minutes=60,
        availability=_shift(), busy=[busy_window],
        slot_minutes=15, tz=UTC,
    )
    assert window.start == datetime(2026, 8, 19, 9, tzinfo=UTC)


def test_overflows_the_shift_when_nothing_fits() -> None:
    window = fit_window(
        worker_id="w-1", day=date(2026, 8, 19), minutes=180,
        availability=_shift(), busy=[_window(8, 15)],
        slot_minutes=15, tz=UTC,
    )
    assert window.start == datetime(2026, 8, 19, 15, tzinfo=UTC)
    assert window.end == datetime(2026, 8, 19, 18, tzinfo=UTC)
    assert window.end > _shift()[0].window.end


def test_without_any_shift_starts_at_the_day_and_overflows() -> None:
    window = fit_window(
        worker_id="w-1", day=date(2026, 8, 19), minutes=60,
        availability=[], busy=[], slot_minutes=15, tz=UTC,
    )
    assert window.start == datetime(2026, 8, 19, 0, tzinfo=UTC)
    assert window.end - window.start == timedelta(minutes=60)
