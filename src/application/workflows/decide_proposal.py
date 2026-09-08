"""Gate explícito de decisão humana sobre uma proposta."""

from domain.planning.entities import HumanDecision, ScheduleProposal
from domain.planning.enums import DecisionType, ProposalStatus


def decide_proposal(
    proposal: ScheduleProposal,
    decision: HumanDecision,
) -> ScheduleProposal:
    if decision.proposal_id != proposal.proposal_id:
        raise ValueError("decision does not reference this proposal")
    if proposal.status not in {ProposalStatus.DRAFT, ProposalStatus.INVALID}:
        raise ValueError("proposal already has a terminal decision")
    if decision.decision is DecisionType.APPROVE:
        if not proposal.verification.valid:
            raise ValueError("an invalid proposal cannot be approved")
        status = ProposalStatus.APPROVED
    else:
        status = ProposalStatus.REJECTED
    return proposal.model_copy(update={"status": status, "decision": decision})
