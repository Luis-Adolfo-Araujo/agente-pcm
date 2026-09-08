from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from infrastructure.database.tractian.mapper import (
    MappingReport,
    map_assignments,
    map_availability,
    map_history,
    map_inventory,
    map_operations,
    map_requirements,
    map_workers,
    snapshot_identity,
)

NOW = datetime(2026, 7, 27, 18, tzinfo=UTC)


def operation_row(
    operation_id: str,
    *,
    source_priority_order: int | None = 4,
    source_criticality_sensitivity: int | None = 5,
) -> dict[str, object]:
    return {
        "work_order_id": f"wo-{operation_id}",
        "operation_id": operation_id,
        "title": "Inspecionar redutor",
        "status": "open",
        "planning_status": "unplanned",
        "created_at": NOW,
        "due_at": None,
        "source_priority_order": source_priority_order,
        "source_criticality_sensitivity": source_criticality_sensitivity,
        "asset_id": "asset-1",
        "location_id": None,
        "activity_type_id": None,
        "planned_team_id": "team-1",
        "planned_duration_minutes": 10,
        "required_worker_count": 1,
        "blocked": False,
        "block_reason": None,
    }


def test_maps_source_scales_and_injects_requirements_without_extra_kwargs() -> None:
    requirements = map_requirements(
        (
            {
                "operation_id": "op-1",
                "item_id": UUID("2d36357c-7373-4b2d-95c3-87b96f1c51a8"),
                "quantity": Decimal("1.50"),
            },
            {
                "operation_id": "op-1",
                "item_id": UUID("2d36357c-7373-4b2d-95c3-87b96f1c51a8"),
                "quantity": Decimal("0.50"),
            },
        )
    )

    operation = map_operations((operation_row("op-1"),), requirements)[0]

    assert operation.priority_level == 1
    assert operation.criticality == 100
    assert operation.planned_duration_minutes == 10
    assert [line.quantity for line in operation.required_materials] == [1.5, 0.5]
    assert all(
        line.item_id == "2d36357c-7373-4b2d-95c3-87b96f1c51a8"
        for line in operation.required_materials
    )


def test_maps_all_known_priority_and_sensitivity_values() -> None:
    rows = tuple(
        operation_row(
            f"op-{source_order}",
            source_priority_order=source_order,
            source_criticality_sensitivity=sensitivity,
        )
        for source_order, sensitivity in ((4, 5), (3, 4), (2, 3), (1, 1))
    )

    operations = map_operations(rows, {})

    assert [operation.priority_level for operation in operations] == [1, 2, 3, 4]
    assert [operation.criticality for operation in operations] == [100, 80, 60, 20]
    assert all(operation.required_materials == () for operation in operations)


def test_invalid_or_missing_source_levels_remain_explicitly_missing() -> None:
    rows = (
        operation_row(
            "missing",
            source_priority_order=None,
            source_criticality_sensitivity=None,
        ),
        operation_row(
            "invalid",
            source_priority_order=99,
            source_criticality_sensitivity=-1,
        ),
    )

    operations = map_operations(rows, {})

    assert [(item.priority_level, item.criticality) for item in operations] == [
        (None, None),
        (None, None),
    ]


def test_maps_empty_postgres_arrays_to_empty_tuples() -> None:
    history = map_history(
        (
            {
                "work_order_id": "wo-1",
                "operation_id": "op-1",
                "title": "Inspeção",
                "finished_at": NOW,
                "duration_minutes": 55,
                "worker_ids": [],
                "asset_id": None,
                "location_id": None,
                "activity_type_id": None,
                "team_id": None,
            },
        )
    )
    workers = map_workers(({"worker_id": "worker-1", "team_ids": []},))

    assert history[0].worker_ids == ()
    assert workers[0].team_ids == ()


def test_maps_inventory_and_time_windows_from_query_contracts() -> None:
    inventory = map_inventory(
        (
            {
                "item_id": "bearing",
                "on_hand_quantity": Decimal("7.00"),
                "reserved_quantity": Decimal("2.00"),
                "lead_time_days": 3,
            },
        )
    )[0]
    availability = map_availability(
        (
            {
                "worker_id": "worker-1",
                "start": NOW,
                "end": datetime(2026, 7, 27, 20, tzinfo=UTC),
            },
        )
    )[0]
    assignment = map_assignments(
        (
            {
                "operation_id": "op-1",
                "worker_id": "worker-1",
                "start": NOW,
                "end": datetime(2026, 7, 27, 19, tzinfo=UTC),
            },
        )
    )[0]

    assert inventory.net_available_quantity == 5
    assert availability.window.minutes == 120
    assert assignment.window.minutes == 60


def test_empty_query_results_and_snapshot_identity_are_stable() -> None:
    assert map_requirements(()) == {}
    assert map_operations((), {}) == ()
    assert map_inventory(()) == ()
    assert map_history(()) == ()
    assert map_workers(()) == ()
    assert map_availability(()) == ()
    assert map_assignments(()) == ()
    assert snapshot_identity("planta-modelo", NOW, 42) == (
        "tractian:planta-modelo:2026-07-27T18:00:00+00:00:42"
    )


def test_mapping_report_counts_rejected_rows_without_exposing_source_values() -> None:
    report = MappingReport()

    inventory = map_inventory(
        (
            {
                "item_id": "sensitive-item-id",
                "on_hand_quantity": -1,
                "reserved_quantity": 0,
                "lead_time_days": None,
            },
        ),
        report=report,
    )

    assert inventory == ()
    assert report.as_metadata() == {
        "rejected_records": 1,
        "rejected_by_domain": {"inventory": 1},
        "rejected_by_error": {"ValidationError": 1},
    }
    assert "sensitive-item-id" not in repr(report)
