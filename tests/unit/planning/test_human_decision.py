from datetime import UTC, datetime

import pytest

from application.workflows.decide_proposal import decide_proposal
from domain.planning.entities import (
    HumanDecision,
    ScheduleProposal,
    SchedulingSolution,
    TimeWindow,
    VerificationReport,
)
from domain.planning.enums import (
    DecisionType,
    ProposalStatus,
    SolutionStatus,
)


def proposal(*, valid: bool) -> ScheduleProposal:
    at = datetime(2026, 8, 17, tzinfo=UTC)
    return ScheduleProposal(
        proposal_id="proposal-1",
        tenant_id="planta-modelo",
        snapshot_id="snapshot-1",
        created_at=at,
        period=TimeWindow(
            start=datetime(2026, 8, 18, tzinfo=UTC),
            end=datetime(2026, 8, 19, tzinfo=UTC),
        ),
        status=ProposalStatus.DRAFT if valid else ProposalStatus.INVALID,
        solution=SchedulingSolution(
            status=SolutionStatus.FEASIBLE,
            assignments=(),
            unscheduled=(),
            objective_value=0,
            algorithm_version="test",
        ),
        verification=VerificationReport(valid=valid, input_hash="hash", violations=()),
        ruleset_version="1",
        weights_version="1",
    )


def decision(kind: DecisionType) -> HumanDecision:
    return HumanDecision(
        proposal_id="proposal-1",
        decision=kind,
        decided_by="pcm-user",
        decided_at=datetime(2026, 8, 17, 13, tzinfo=UTC),
        reason="Revisão humana concluída",
    )


def test_valid_proposal_can_be_approved() -> None:
    approved = decide_proposal(proposal(valid=True), decision(DecisionType.APPROVE))
    assert approved.status is ProposalStatus.APPROVED
    assert approved.decision is not None
    assert approved.decision.decided_by == "pcm-user"


def test_invalid_proposal_cannot_be_approved_but_can_be_rejected() -> None:
    invalid = proposal(valid=False)
    with pytest.raises(ValueError, match="cannot be approved"):
        decide_proposal(invalid, decision(DecisionType.APPROVE))

    rejected = decide_proposal(invalid, decision(DecisionType.REJECT))
    assert rejected.status is ProposalStatus.REJECTED
