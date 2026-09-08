"""Porta de persistência de propostas e decisões humanas."""

from typing import Protocol

from domain.planning.entities import ScheduleProposal


class ProposalRepository(Protocol):
    def save(self, proposal: ScheduleProposal) -> None: ...

    def get(self, proposal_id: str) -> ScheduleProposal | None: ...
