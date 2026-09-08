"""Porta de leitura do snapshot canônico."""

from datetime import datetime
from typing import Protocol

from domain.planning.entities import PlanningSnapshot, TimeWindow


class PlanningRepository(Protocol):
    def load_snapshot(
        self,
        *,
        tenant_id: str,
        as_of: datetime,
        period: TimeWindow,
    ) -> PlanningSnapshot: ...
