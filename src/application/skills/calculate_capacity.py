"""Caso de uso da skill de capacidade."""

from domain.planning.capacity import calculate_capacity
from domain.planning.entities import (
    AvailabilitySlot,
    CapacityAssessment,
    ExistingAssignment,
    TimeWindow,
    WorkerProfile,
)


def run_calculate_capacity(
    workers: tuple[WorkerProfile, ...],
    availability: tuple[AvailabilitySlot, ...],
    assignments: tuple[ExistingAssignment, ...],
    period: TimeWindow,
) -> tuple[CapacityAssessment, ...]:
    return calculate_capacity(workers, availability, assignments, period)
