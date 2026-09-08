"""Cobertura de capacidade: separa limite físico de falha de recomendação.

Sem este indicador, uma semana com muitas operações não programadas é lida como
erro do agente, quando na maior parte dos casos é a mão de obra disponível que
não comporta o backlog.
"""

from __future__ import annotations

from application.pilot.models import CapacityCoverage
from domain.planning.entities import PlanningRunResult
from domain.planning.enums import UnscheduledReason


def capacity_coverage(result: PlanningRunResult) -> CapacityCoverage:
    demand_minutes = sum(
        (item.duration.minutes or 0) * item.operation.required_worker_count
        for item in result.enriched
    )
    available_minutes = sum(item.net_minutes for item in result.capacities)
    solution = result.proposal.solution
    reasons: dict[str, int] = {}
    for item in solution.unscheduled:
        reasons[item.reason.value] = reasons.get(item.reason.value, 0) + 1
    percent = (
        0.0
        if demand_minutes == 0
        else round(min(available_minutes / demand_minutes, 1.0) * 100, 2)
    )
    return CapacityCoverage(
        total_operations=len(result.enriched),
        scheduled_operations=len(solution.assignments),
        unscheduled_operations=len(solution.unscheduled),
        capacity_limited_operations=reasons.get(UnscheduledReason.NO_CAPACITY.value, 0),
        demand_minutes=demand_minutes,
        available_minutes=available_minutes,
        coverage_percent=percent,
        reasons=reasons,
    )


__all__ = ["capacity_coverage"]
