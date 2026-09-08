"""Caso de uso da skill de ranking."""

from datetime import datetime

from domain.planning.config import RankingConfig
from domain.planning.entities import PriorityAssessment, WorkOrderOperation
from domain.planning.ranking import rank_operations


def run_rank_backlog(
    operations: tuple[WorkOrderOperation, ...],
    as_of: datetime,
    config: RankingConfig,
) -> tuple[PriorityAssessment, ...]:
    return rank_operations(operations, as_of, config)
