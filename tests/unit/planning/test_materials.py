from datetime import UTC, datetime

import pytest

from domain.planning.config import MaterialConfig
from domain.planning.entities import (
    InventoryPosition,
    MaterialRequirement,
    WorkOrderOperation,
)
from domain.planning.enums import MaterialStatus
from domain.planning.materials import assess_materials

PERIOD_END = datetime(2026, 8, 21, 18, tzinfo=UTC)


def operation(
    operation_id: str, *requirements: MaterialRequirement
) -> WorkOrderOperation:
    return WorkOrderOperation(
        work_order_id=f"wo-{operation_id}",
        operation_id=operation_id,
        status="open",
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        required_materials=requirements,
    )


def test_separates_all_material_statuses() -> None:
    operations = (
        operation("nao-cadastrado"),
        operation("unknown", MaterialRequirement(item_id="missing", quantity=1)),
        operation("unavailable", MaterialRequirement(item_id="empty", quantity=2)),
        operation("partial", MaterialRequirement(item_id="low", quantity=4)),
        operation("available", MaterialRequirement(item_id="enough", quantity=3)),
    )
    inventory = (
        InventoryPosition(item_id="empty", on_hand_quantity=0),
        InventoryPosition(item_id="low", on_hand_quantity=3, reserved_quantity=1),
        InventoryPosition(item_id="enough", on_hand_quantity=6, reserved_quantity=2),
    )

    result = assess_materials(operations, inventory, PERIOD_END, MaterialConfig())

    assert [assessment.status for assessment in result] == [
        MaterialStatus.UNKNOWN,
        MaterialStatus.UNKNOWN,
        MaterialStatus.UNAVAILABLE,
        MaterialStatus.PARTIAL,
        MaterialStatus.AVAILABLE,
    ]
    assert [assessment.blocking for assessment in result] == [False, True, True, True, False]
    partial_line = result[3].lines[0]
    assert partial_line.available_quantity == 2
    assert partial_line.missing_quantity == 2


def test_aggregates_requirements_and_inventory_positions_by_item() -> None:
    candidate = operation(
        "op-1",
        MaterialRequirement(item_id="bearing", quantity=2),
        MaterialRequirement(item_id="bearing", quantity=3),
    )
    inventory = (
        InventoryPosition(item_id="bearing", on_hand_quantity=4, reserved_quantity=1),
        InventoryPosition(item_id="bearing", on_hand_quantity=3, reserved_quantity=1),
    )

    assessment = assess_materials(
        (candidate,), inventory, PERIOD_END, MaterialConfig()
    )[0]

    assert assessment.status is MaterialStatus.AVAILABLE
    assert len(assessment.lines) == 1
    assert assessment.lines[0].required_quantity == 5
    assert assessment.lines[0].available_quantity == 5


def test_expected_inbound_without_quantity_remains_blocking() -> None:
    candidate = operation("op-1", MaterialRequirement(item_id="bearing", quantity=2))
    inventory = (
        InventoryPosition(
            item_id="bearing",
            on_hand_quantity=0,
            expected_inbound_at=datetime(2026, 8, 20, tzinfo=UTC),
        ),
    )

    assessment = assess_materials(
        (candidate,), inventory, PERIOD_END, MaterialConfig(consider_expected_inbound=True)
    )[0]

    assert assessment.status is MaterialStatus.UNAVAILABLE
    assert assessment.blocking is True
    assert assessment.lines[0].available_quantity == 0
    assert assessment.lines[0].missing_quantity == 2
    assert assessment.lines[0].reason_code == "expected_inbound_quantity_unknown"


def test_partial_stock_can_be_allowed_by_configuration() -> None:
    candidate = operation("op-1", MaterialRequirement(item_id="bearing", quantity=2))
    inventory = (InventoryPosition(item_id="bearing", on_hand_quantity=1),)

    assessment = assess_materials(
        (candidate,), inventory, PERIOD_END, MaterialConfig(allow_partial=True)
    )[0]

    assert assessment.status is MaterialStatus.PARTIAL
    assert assessment.blocking is False
    assert assessment.lines[0].reason_code == "partial_material_allowed"


def test_reservation_for_operation_is_available_only_to_that_operation() -> None:
    candidate = operation(
        "op-1",
        MaterialRequirement(item_id="bearing", quantity=2, reserved_quantity=2),
    )
    inventory = (
        InventoryPosition(item_id="bearing", on_hand_quantity=2, reserved_quantity=2),
    )

    assessment = assess_materials(
        (candidate,), inventory, PERIOD_END, MaterialConfig()
    )[0]

    assert assessment.status is MaterialStatus.AVAILABLE
    assert assessment.blocking is False
    assert assessment.lines[0].reserved_for_operation == 2
    assert assessment.lines[0].reason_code == "material_available_including_reservation"


def test_rejects_naive_period_end() -> None:
    with pytest.raises(ValueError, match="period_end must include a timezone"):
        assess_materials((), (), datetime(2026, 8, 21, 18), MaterialConfig())


def test_operation_without_registered_material_is_unknown_not_not_required() -> None:
    """Ausência de cadastro no Planta Modelo significa diagnóstico ou saldo desconhecido.

    Não significa que a operação dispensa material, então o status não pode
    afirmar prontidão.
    """

    assessment = assess_materials(
        (operation("sem-cadastro"),),
        (),
        PERIOD_END,
        MaterialConfig(),
    )[0]

    assert assessment.status is MaterialStatus.UNKNOWN
    assert "material_requirement_not_registered" in assessment.reason_codes


def test_unregistered_material_does_not_block_the_pilot_by_default() -> None:
    assessment = assess_materials(
        (operation("sem-cadastro"),),
        (),
        PERIOD_END,
        MaterialConfig(),
    )[0]

    assert assessment.blocking is False


def test_unregistered_material_blocks_when_the_policy_demands_evidence() -> None:
    assessment = assess_materials(
        (operation("sem-cadastro"),),
        (),
        PERIOD_END,
        MaterialConfig(block_unregistered_material=True),
    )[0]

    assert assessment.status is MaterialStatus.UNKNOWN
    assert assessment.blocking is True
