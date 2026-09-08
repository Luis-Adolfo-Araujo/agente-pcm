"""Caso de uso da skill de duração."""

from datetime import datetime

from domain.planning.config import DurationConfig
from domain.planning.duration import estimate_durations
from domain.planning.entities import DurationEstimate, HistoricalExecution, WorkOrderOperation


def run_estimate_duration(
    operations: tuple[WorkOrderOperation, ...],
    history: tuple[HistoricalExecution, ...],
    as_of: datetime,
    config: DurationConfig,
) -> tuple[DurationEstimate, ...]:
    return estimate_durations(operations, history, as_of, config)
