"""Ranking determinístico do backlog de manutenção.

O módulo não consulta relógio, banco ou modelo externo. O instante ``as_of`` e a
configuração recebidos são toda a informação necessária para reproduzir o score.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from domain.planning.config import RankingConfig
from domain.planning.entities import PriorityAssessment, ScoreComponent, WorkOrderOperation

_SECONDS_PER_DAY = 24 * 60 * 60


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("as_of must include a timezone")


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return min(upper, max(lower, value))


def _age(operation: WorkOrderOperation, as_of: datetime, cap_days: int) -> tuple[float, float]:
    raw_days = (as_of - operation.created_at).total_seconds() / _SECONDS_PER_DAY
    effective_days = max(0.0, raw_days)
    normalized = _clamp(effective_days / cap_days * 100.0)
    return raw_days, normalized


def _sla(
    operation: WorkOrderOperation,
    as_of: datetime,
    config: RankingConfig,
) -> tuple[float, float, str]:
    """Return days remaining, normalized urgency and its reason code.

    The first half of the 0--100 scale represents a due date approaching within
    ``sla_horizon_days``. The second half represents an overdue order, capped at
    ``overdue_cap_days``. This preserves a useful distinction between "due now"
    and "overdue for a long time".
    """

    if operation.due_at is None:
        return 0.0, 0.0, "SLA_MISSING"

    days_remaining = (operation.due_at - as_of).total_seconds() / _SECONDS_PER_DAY
    if days_remaining < 0:
        overdue_days = -days_remaining
        normalized = 50.0 + 50.0 * min(overdue_days / config.overdue_cap_days, 1.0)
        return days_remaining, normalized, "SLA_OVERDUE"

    normalized = 50.0 * max(0.0, 1.0 - days_remaining / config.sla_horizon_days)
    if days_remaining == 0:
        reason = "SLA_DUE_NOW"
    elif days_remaining <= config.sla_horizon_days:
        reason = "SLA_APPROACHING"
    else:
        reason = "SLA_OUTSIDE_HORIZON"
    return days_remaining, normalized, reason


def _band(score: float) -> str:
    if score >= 80:
        return "very_high"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _assessment(
    operation: WorkOrderOperation,
    as_of: datetime,
    config: RankingConfig,
) -> PriorityAssessment:
    has_criticality = operation.criticality is not None
    model = "model_b" if has_criticality else "model_a"

    configured_weights = {
        "priority": config.priority_weight,
        "age": config.age_weight,
        "sla": config.sla_weight,
    }
    if has_criticality:
        configured_weights["criticality"] = config.criticality_weight

    total_weight = sum(configured_weights.values())

    def effective_weight(name: str) -> float:
        if total_weight == 0:
            return 0.0
        return configured_weights[name] / total_weight

    missing_fields: list[str] = []
    reason_codes: list[str] = []

    priority_level = operation.priority_level
    if priority_level is None or priority_level not in config.priority_scores:
        priority_raw = float(priority_level or 0)
        priority_normalized = 0.0
        missing_fields.append("priority_level")
        reason_codes.append("PRIORITY_MISSING")
    else:
        priority_raw = float(priority_level)
        priority_normalized = _clamp(float(config.priority_scores[priority_level]))
        reason_codes.append("PRIORITY_APPLIED")

    age_raw, age_normalized = _age(operation, as_of, config.age_cap_days)
    if age_raw < 0:
        reason_codes.append("CREATED_AFTER_AS_OF")
    elif age_raw >= config.age_cap_days:
        reason_codes.append("AGE_CAPPED")
    else:
        reason_codes.append("AGE_APPLIED")

    sla_raw, sla_normalized, sla_reason = _sla(operation, as_of, config)
    reason_codes.append(sla_reason)
    if operation.due_at is None:
        missing_fields.append("due_at")

    raw_components = [
        ("priority", priority_raw, priority_normalized),
        ("age", age_raw, age_normalized),
        ("sla", sla_raw, sla_normalized),
    ]

    if has_criticality:
        assert operation.criticality is not None
        raw_components.append(
            ("criticality", float(operation.criticality), float(operation.criticality))
        )
        reason_codes.append("CRITICALITY_APPLIED")
    else:
        missing_fields.append("criticality")
        reason_codes.append("CRITICALITY_MISSING")

    components = tuple(
        ScoreComponent(
            name=name,
            raw_value=round(raw_value, 6),
            normalized_value=round(_clamp(normalized_value), 6),
            weight=round(effective_weight(name), 12),
            contribution=round(_clamp(normalized_value) * effective_weight(name), 6),
        )
        for name, raw_value, normalized_value in raw_components
    )
    score = round(sum(component.contribution for component in components), 6)

    return PriorityAssessment(
        operation_id=operation.operation_id,
        score=_clamp(score),
        band=_band(score),
        model=model,
        components=components,
        reason_codes=tuple(reason_codes),
        missing_fields=tuple(missing_fields),
    )


def rank_operations(
    operations: Iterable[WorkOrderOperation],
    as_of: datetime,
    config: RankingConfig,
) -> tuple[PriorityAssessment, ...]:
    """Score and stably order operations from most to least urgent.

    Ties are resolved by earliest due date, oldest creation date, work-order ID,
    and operation ID. Consequently, the result does not depend on input order.
    Missing priority or SLA contributes zero and is reported explicitly; its
    configured weight is not redistributed because that would reward incomplete
    records. Criticality is the optional distinction between model A and B.
    """

    _require_aware(as_of)
    assessed = [(operation, _assessment(operation, as_of, config)) for operation in operations]
    assessed.sort(
        key=lambda item: (
            -item[1].score,
            item[0].due_at is None,
            item[0].due_at.timestamp() if item[0].due_at is not None else float("inf"),
            item[0].created_at.timestamp(),
            item[0].work_order_id,
            item[0].operation_id,
        )
    )
    return tuple(assessment for _, assessment in assessed)
