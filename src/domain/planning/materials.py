"""Avalia, de forma determinística, a prontidão de materiais das operações."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from domain.planning.config import MaterialConfig
from domain.planning.entities import (
    InventoryPosition,
    MaterialAssessment,
    MaterialLineAssessment,
    WorkOrderOperation,
)
from domain.planning.enums import MaterialStatus

_QUANTITY_EPSILON = 1e-9


def assess_materials(
    operations: Sequence[WorkOrderOperation],
    inventory: Sequence[InventoryPosition],
    period_end: datetime,
    config: MaterialConfig,
) -> tuple[MaterialAssessment, ...]:
    """Retorna a situação de materiais de cada operação.

    O status descreve o saldo conhecido no instante do snapshot. Uma entrada
    prevista sem quantidade confirmada não retira o bloqueio. Reservas vinculadas
    à própria operação são somadas ao saldo líquido disponível para ela.
    """

    _require_aware(period_end, "period_end")
    positions_by_item: dict[str, list[InventoryPosition]] = defaultdict(list)
    for position in inventory:
        positions_by_item[position.item_id].append(position)

    assessments: list[MaterialAssessment] = []
    for operation in operations:
        requirements: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
        for requirement in operation.required_materials:
            requirements[requirement.item_id][0] += requirement.quantity
            requirements[requirement.item_id][1] += requirement.reserved_quantity

        if not requirements:
            # Sem requisito cadastrado não há evidência de dispensa de material.
            # A ausência costuma significar diagnóstico pendente ou item sem saldo,
            # então a prontidão fica desconhecida em vez de afirmada.
            assessments.append(
                MaterialAssessment(
                    operation_id=operation.operation_id,
                    status=MaterialStatus.UNKNOWN,
                    blocking=config.block_unregistered_material,
                    reason_codes=(
                        "material_unknown",
                        "material_requirement_not_registered",
                    ),
                )
            )
            continue

        lines = tuple(
            _assess_line(
                item_id=item_id,
                required_quantity=quantities[0],
                reserved_for_operation=min(quantities[0], quantities[1]),
                positions=positions_by_item.get(item_id, ()),
                period_end=period_end,
                config=config,
            )
            for item_id, quantities in sorted(requirements.items())
        )
        status = _assessment_status(lines)
        line_reason_codes = tuple(dict.fromkeys(line.reason_code for line in lines))
        reason_codes = tuple(
            dict.fromkeys((f"material_{status.value}", *line_reason_codes))
        )
        assessments.append(
            MaterialAssessment(
                operation_id=operation.operation_id,
                status=status,
                blocking=any(line.blocking for line in lines),
                lines=lines,
                reason_codes=reason_codes,
            )
        )

    return tuple(assessments)


def _assess_line(
    *,
    item_id: str,
    required_quantity: float,
    reserved_for_operation: float,
    positions: Sequence[InventoryPosition],
    period_end: datetime,
    config: MaterialConfig,
) -> MaterialLineAssessment:
    if not positions:
        return MaterialLineAssessment(
            item_id=item_id,
            required_quantity=required_quantity,
            available_quantity=None,
            reserved_for_operation=reserved_for_operation,
            missing_quantity=None,
            lead_time_days=None,
            blocking=True,
            reason_code="inventory_position_missing",
        )

    available_quantity = (
        sum(position.net_available_quantity for position in positions)
        + reserved_for_operation
    )
    missing_quantity = required_quantity - available_quantity
    if missing_quantity <= _QUANTITY_EPSILON:
        missing_quantity = 0.0
    known_lead_times = [
        position.lead_time_days
        for position in positions
        if position.lead_time_days is not None
    ]
    lead_time_days = min(known_lead_times) if known_lead_times else None

    if missing_quantity == 0:
        blocking = False
        reason_code = (
            "material_available_including_reservation"
            if reserved_for_operation > 0
            else "material_available"
        )
    else:
        inbound_dates = [
            position.expected_inbound_at
            for position in positions
            if position.expected_inbound_at is not None
        ]
        inbound_by_period_end = any(inbound_at <= period_end for inbound_at in inbound_dates)

        if config.consider_expected_inbound and inbound_by_period_end:
            # O contrato informa a data, mas não a quantidade da entrada.
            # Manter o bloqueio evita prometer um material sem evidência de saldo.
            blocking = True
            reason_code = "expected_inbound_quantity_unknown"
        elif _QUANTITY_EPSILON < available_quantity < required_quantity:
            blocking = not config.allow_partial
            reason_code = (
                "partial_material_allowed"
                if config.allow_partial
                else "material_partially_available"
            )
        elif inbound_dates and min(inbound_dates) > period_end:
            blocking = True
            reason_code = "expected_inbound_after_period_end"
        elif inbound_dates and not config.consider_expected_inbound:
            blocking = True
            reason_code = "expected_inbound_ignored"
        else:
            blocking = True
            reason_code = "material_unavailable"

    return MaterialLineAssessment(
        item_id=item_id,
        required_quantity=required_quantity,
        available_quantity=available_quantity,
        reserved_for_operation=reserved_for_operation,
        missing_quantity=missing_quantity,
        lead_time_days=lead_time_days,
        blocking=blocking,
        reason_code=reason_code,
    )


def _assessment_status(lines: Sequence[MaterialLineAssessment]) -> MaterialStatus:
    if any(line.available_quantity is None for line in lines):
        return MaterialStatus.UNKNOWN
    if all(line.missing_quantity == 0 for line in lines):
        return MaterialStatus.AVAILABLE
    if all((line.available_quantity or 0.0) <= _QUANTITY_EPSILON for line in lines):
        return MaterialStatus.UNAVAILABLE
    return MaterialStatus.PARTIAL


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
