"""Caso de uso da skill de executantes."""

from datetime import datetime

from domain.planning.config import ExecutantConfig
from domain.planning.entities import (
    CapacityAssessment,
    DurationEstimate,
    ExecutorCandidate,
    HistoricalExecution,
    WorkerProfile,
    WorkOrderOperation,
)
from domain.planning.executants import suggest_executants


def run_suggest_executants(
    operations: tuple[WorkOrderOperation, ...],
    durations: tuple[DurationEstimate, ...],
    capacities: tuple[CapacityAssessment, ...],
    workers: tuple[WorkerProfile, ...],
    history: tuple[HistoricalExecution, ...],
    as_of: datetime,
    config: ExecutantConfig,
) -> dict[str, tuple[ExecutorCandidate, ...]]:
    return suggest_executants(
        operations,
        durations,
        capacities,
        workers,
        history,
        as_of,
        config,
    )
