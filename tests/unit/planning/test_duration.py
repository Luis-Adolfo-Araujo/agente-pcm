from datetime import UTC, datetime, timedelta

import pytest

from domain.planning.config import DurationConfig
from domain.planning.duration import estimate_durations
from domain.planning.entities import HistoricalExecution, WorkOrderOperation
from domain.planning.enums import DurationSource

AS_OF = datetime(2026, 7, 1, 12, tzinfo=UTC)


def operation(
    operation_id: str = "target",
    *,
    planned_minutes: int | None = None,
    asset_id: str | None = "asset-1",
    location_id: str | None = "location-1",
    activity_type_id: str | None = "activity-1",
    title: str = "Trocar rolamento do motor",
) -> WorkOrderOperation:
    return WorkOrderOperation(
        work_order_id=f"wo-{operation_id}",
        operation_id=operation_id,
        title=title,
        status="open",
        created_at=AS_OF - timedelta(days=3),
        planned_duration_minutes=planned_minutes,
        asset_id=asset_id,
        location_id=location_id,
        activity_type_id=activity_type_id,
    )


def execution(
    suffix: str,
    minutes: int,
    *,
    finished_at: datetime | None = None,
    asset_id: str | None = "asset-1",
    location_id: str | None = "location-1",
    activity_type_id: str | None = "activity-1",
    title: str = "Troca de rolamento do motor",
) -> HistoricalExecution:
    return HistoricalExecution(
        work_order_id=f"historical-wo-{suffix}",
        operation_id=f"historical-op-{suffix}",
        title=title,
        finished_at=finished_at or AS_OF - timedelta(days=1),
        duration_minutes=minutes,
        asset_id=asset_id,
        location_id=location_id,
        activity_type_id=activity_type_id,
    )


def test_valid_planned_duration_is_preferred() -> None:
    result = estimate_durations(
        (operation(planned_minutes=75),),
        (execution("one", 20), execution("two", 30), execution("three", 40)),
        AS_OF,
        DurationConfig(),
    )[0]

    assert result.minutes == 75
    assert result.p50_minutes == 75
    assert result.p80_minutes == 75
    assert result.source is DurationSource.PLANNED
    assert result.sample_size == 0
    assert result.confidence == 1


def test_uses_median_and_nearest_rank_p80_from_most_specific_history() -> None:
    history = tuple(
        execution(str(index), minutes) for index, minutes in enumerate((30, 60, 90, 120, 150))
    )

    result = estimate_durations(
        (operation(),), history, AS_OF, DurationConfig(minimum_sample_size=3)
    )[0]

    assert result.source is DurationSource.SAME_ACTIVITY_AND_ASSET
    assert result.minutes == 90
    assert result.p50_minutes == 90
    assert result.p80_minutes == 120
    assert result.sample_size == 5
    assert 0 < result.confidence < 1


def test_future_and_implausibly_long_history_are_ignored() -> None:
    history = (
        execution("valid-1", 40),
        execution("valid-2", 50),
        execution("future", 1, finished_at=AS_OF + timedelta(seconds=1)),
        execution("too-long", 2_000),
    )
    config = DurationConfig(minimum_sample_size=2, maximum_valid_minutes=1_440)

    result = estimate_durations((operation(),), history, AS_OF, config)[0]

    assert result.source is DurationSource.SAME_ACTIVITY_AND_ASSET
    assert result.sample_size == 2
    assert result.minutes == 45
    assert result.p80_minutes == 50


def test_falls_back_through_asset_activity_location_and_title() -> None:
    target = operation(asset_id=None, activity_type_id=None, location_id=None)
    history = (
        execution("one", 30, asset_id=None, activity_type_id=None, location_id=None),
        execution("two", 50, asset_id=None, activity_type_id=None, location_id=None),
        execution("three", 70, asset_id=None, activity_type_id=None, location_id=None),
    )

    result = estimate_durations((target,), history, AS_OF, DurationConfig())[0]

    assert result.source is DurationSource.SIMILAR_TITLE
    assert result.minutes == 50


def test_falls_back_to_configured_default_when_history_is_insufficient() -> None:
    result = estimate_durations(
        (operation(asset_id=None, activity_type_id=None, location_id=None, title="unique"),),
        (execution("only", 45, title="unrelated"),),
        AS_OF,
        DurationConfig(minimum_sample_size=3, default_minutes=80),
    )[0]

    assert result.source is DurationSource.DEFAULT
    assert result.minutes == 80
    assert result.sample_size == 0
    assert result.confidence == pytest.approx(0.2)
    assert "INSUFFICIENT_HISTORY" in result.reason_codes


def test_can_report_duration_as_unavailable() -> None:
    result = estimate_durations(
        (operation(planned_minutes=None),),
        (),
        AS_OF,
        DurationConfig(default_minutes=None),
    )[0]

    assert result.source is DurationSource.UNAVAILABLE
    assert result.minutes is None
    assert result.p50_minutes is None
    assert result.p80_minutes is None
    assert result.confidence == 0


def test_output_preserves_operation_order() -> None:
    operations = (operation("second", planned_minutes=20), operation("first", planned_minutes=10))

    result = estimate_durations(operations, (), AS_OF, DurationConfig())

    assert [item.operation_id for item in result] == ["second", "first"]


def test_naive_as_of_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone"):
        estimate_durations(
            (operation(),), (), AS_OF.replace(tzinfo=None), DurationConfig()
        )
