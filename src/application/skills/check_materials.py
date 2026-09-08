"""Caso de uso da skill de materiais."""

from datetime import datetime

from domain.planning.config import MaterialConfig
from domain.planning.entities import (
    InventoryPosition,
    MaterialAssessment,
    WorkOrderOperation,
)
from domain.planning.materials import assess_materials


def run_check_materials(
    operations: tuple[WorkOrderOperation, ...],
    inventory: tuple[InventoryPosition, ...],
    period_end: datetime,
    config: MaterialConfig,
) -> tuple[MaterialAssessment, ...]:
    return assess_materials(operations, inventory, period_end, config)
