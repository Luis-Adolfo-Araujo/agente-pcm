from datetime import UTC, datetime, timedelta

import pytest

from domain.planning.config import RankingConfig
from domain.planning.entities import WorkOrderOperation
from domain.planning.ranking import rank_operations

AS_OF = datetime(2026, 7, 1, 12, tzinfo=UTC)


def operation(
    operation_id: str,
    *,
    age_days: int = 1,
    due_in_days: int | None = 10,
    priority_level: int | None = 2,
    criticality: int | None = None,
) -> WorkOrderOperation:
    return WorkOrderOperation(
        work_order_id=f"wo-{operation_id}",
        operation_id=operation_id,
        status="open",
        created_at=AS_OF - timedelta(days=age_days),
        due_at=None if due_in_days is None else AS_OF + timedelta(days=due_in_days),
        priority_level=priority_level,
        criticality=criticality,
    )


def test_reference_case_old_medium_ranks_above_new_high() -> None:
    medium_old = operation("medium-old", age_days=30, due_in_days=0, priority_level=3)
    high_new = operation("high-new", age_days=1, due_in_days=9, priority_level=2)

    result = rank_operations((high_new, medium_old), AS_OF, RankingConfig())

    assert [item.operation_id for item in result] == ["medium-old", "high-new"]


def test_model_b_uses_criticality_and_normalizes_all_weights() -> None:
    result = rank_operations(
        (operation("critical", criticality=100),),
        AS_OF,
        RankingConfig(),
    )[0]

    assert result.model == "model_b"
    assert result.score <= 100
    assert sum(component.contribution for component in result.components) == pytest.approx(
        result.score, abs=1e-5
    )
    assert sum(component.weight for component in result.components) == pytest.approx(1.0)
    assert "criticality" not in result.missing_fields
    assert "CRITICALITY_APPLIED" in result.reason_codes


def test_model_a_does_not_silently_impute_criticality() -> None:
    result = rank_operations((operation("without-criticality"),), AS_OF, RankingConfig())[0]

    assert result.model == "model_a"
    assert "criticality" in result.missing_fields
    assert all(component.name != "criticality" for component in result.components)
    assert "CRITICALITY_MISSING" in result.reason_codes


def test_missing_priority_and_due_date_are_explicit_and_contribute_zero() -> None:
    result = rank_operations(
        (operation("incomplete", age_days=10, due_in_days=None, priority_level=None),),
        AS_OF,
        RankingConfig(),
    )[0]
    components = {component.name: component for component in result.components}

    assert result.missing_fields == ("priority_level", "due_at", "criticality")
    assert components["priority"].contribution == 0
    assert components["sla"].contribution == 0
    assert result.score == pytest.approx(components["age"].contribution)


def test_as_of_changes_age_and_sla_without_reading_the_clock() -> None:
    candidate = operation("temporal", age_days=5, due_in_days=5)

    before = rank_operations((candidate,), AS_OF, RankingConfig())[0]
    later = rank_operations((candidate,), AS_OF + timedelta(days=10), RankingConfig())[0]

    assert later.score > before.score
    assert "SLA_OVERDUE" in later.reason_codes


def test_tie_break_is_stable_and_independent_of_input_order() -> None:
    later_due = operation("later", due_in_days=2)
    earlier_due = operation("earlier", due_in_days=1)
    # Eliminate the SLA contribution so both records have exactly the same score.
    config = RankingConfig(sla_weight=0)

    first = rank_operations((later_due, earlier_due), AS_OF, config)
    second = rank_operations((earlier_due, later_due), AS_OF, config)

    assert [item.operation_id for item in first] == ["earlier", "later"]
    assert first == second


def test_naive_as_of_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone"):
        rank_operations((operation("one"),), AS_OF.replace(tzinfo=None), RankingConfig())
