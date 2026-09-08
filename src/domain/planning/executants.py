"""Sugestão determinística de executantes para operações de manutenção.

O módulo deliberadamente produz candidatos, e não alocações. A decisão de
quem executará uma operação pertence ao otimizador, que consegue avaliar a
disponibilidade concorrente de todos os profissionais necessários.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime

from domain.planning.config import ExecutantConfig, PlanningConfig
from domain.planning.entities import (
    CapacityAssessment,
    DurationEstimate,
    ExecutorCandidate,
    HistoricalExecution,
    WorkerProfile,
    WorkOrderOperation,
)


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("as_of must include a timezone")


def _duration_index(
    durations: Mapping[str, DurationEstimate] | Iterable[DurationEstimate],
) -> dict[str, DurationEstimate]:
    if isinstance(durations, Mapping):
        return dict(durations)
    return {estimate.operation_id: estimate for estimate in durations}


def _capacity_index(
    capacities: Mapping[str, CapacityAssessment] | Iterable[CapacityAssessment],
) -> dict[str, CapacityAssessment]:
    if isinstance(capacities, Mapping):
        return dict(capacities)
    return {capacity.worker_id: capacity for capacity in capacities}


def _executant_config(config: ExecutantConfig | PlanningConfig) -> ExecutantConfig:
    return config.executants if isinstance(config, PlanningConfig) else config


def _canonical_workers(workers: Iterable[WorkerProfile]) -> tuple[WorkerProfile, ...]:
    """Deduplica perfis de forma estável, preferindo um perfil ativo."""

    grouped: dict[str, list[WorkerProfile]] = defaultdict(list)
    for worker in workers:
        grouped[worker.worker_id].append(worker)

    canonical: list[WorkerProfile] = []
    for worker_id in sorted(grouped):
        canonical.append(
            min(
                grouped[worker_id],
                key=lambda worker: (
                    not worker.active,
                    tuple(sorted(worker.team_ids)),
                    tuple(sorted(worker.qualification_ids)),
                ),
            )
        )
    return tuple(canonical)


def _has_contiguous_capacity(
    operation: WorkOrderOperation,
    capacity: CapacityAssessment,
    minutes: int,
    as_of: datetime,
) -> bool:
    for slot in capacity.slots:
        start = max(slot.window.start, as_of)
        end = slot.window.end
        if operation.operational_windows:
            for operational_window in operation.operational_windows:
                overlap_start = max(start, operational_window.start)
                overlap_end = min(end, operational_window.end)
                if (overlap_end - overlap_start).total_seconds() >= minutes * 60:
                    return True
        elif (end - start).total_seconds() >= minutes * 60:
            return True
    return False


def suggest_executants(
    operations: Iterable[WorkOrderOperation],
    durations: Mapping[str, DurationEstimate] | Iterable[DurationEstimate],
    capacities: Mapping[str, CapacityAssessment] | Iterable[CapacityAssessment],
    workers: Iterable[WorkerProfile],
    history: Iterable[HistoricalExecution],
    as_of: datetime,
    config: ExecutantConfig | PlanningConfig,
) -> dict[str, tuple[ExecutorCandidate, ...]]:
    """Ordena candidatos por compatibilidade histórica e capacidade conhecida.

    Somente execuções concluídas até ``as_of`` são usadas, evitando vazamento
    temporal no backtesting. Experiência histórica nunca é tratada como
    certificação: na ausência de requisitos explícitos no contrato da operação,
    ela afeta apenas o score.
    """

    _require_aware(as_of)
    settings = _executant_config(config)
    duration_by_operation = _duration_index(durations)
    capacity_by_worker = _capacity_index(capacities)
    canonical_workers = _canonical_workers(workers)

    history_by_worker: dict[str, list[HistoricalExecution]] = defaultdict(list)
    frequency: Counter[str] = Counter()
    for execution in history:
        if execution.finished_at > as_of:
            continue
        for worker_id in sorted(set(execution.worker_ids)):
            history_by_worker[worker_id].append(execution)
            frequency[worker_id] += 1

    maximum_frequency = max(frequency.values(), default=0)
    result: dict[str, tuple[ExecutorCandidate, ...]] = {}

    # A ordenação torna a saída independente da ordem recebida no iterável.
    canonical_operations = sorted(operations, key=lambda item: item.operation_id)
    for operation in canonical_operations:
        duration = duration_by_operation.get(operation.operation_id)
        estimated_minutes = duration.minutes if duration is not None else None

        applicable_weight = settings.frequency_weight
        if operation.planned_team_id is not None:
            applicable_weight += settings.team_weight
        if operation.asset_id is not None:
            applicable_weight += settings.asset_weight
        if operation.activity_type_id is not None:
            applicable_weight += settings.activity_weight
        if operation.location_id is not None:
            applicable_weight += settings.location_weight

        candidates: list[ExecutorCandidate] = []
        for worker in canonical_workers:
            capacity = capacity_by_worker.get(worker.worker_id)
            available_minutes = capacity.net_minutes if capacity is not None else 0
            worker_history = history_by_worker.get(worker.worker_id, [])
            reasons: list[str] = []
            weighted_score = 0.0

            if (
                operation.planned_team_id is not None
                and operation.planned_team_id in worker.team_ids
            ):
                weighted_score += settings.team_weight
                reasons.append("TEAM_MATCH")

            if operation.asset_id is not None and any(
                execution.asset_id == operation.asset_id for execution in worker_history
            ):
                weighted_score += settings.asset_weight
                reasons.append("ASSET_EXPERIENCE")

            if operation.activity_type_id is not None and any(
                execution.activity_type_id == operation.activity_type_id
                for execution in worker_history
            ):
                weighted_score += settings.activity_weight
                reasons.append("ACTIVITY_EXPERIENCE")

            if operation.location_id is not None and any(
                execution.location_id == operation.location_id for execution in worker_history
            ):
                weighted_score += settings.location_weight
                reasons.append("LOCATION_EXPERIENCE")

            if maximum_frequency and frequency[worker.worker_id]:
                weighted_score += settings.frequency_weight * (
                    frequency[worker.worker_id] / maximum_frequency
                )
                reasons.append("HISTORICAL_FREQUENCY")

            eligible = True
            if not worker.active:
                eligible = False
                reasons.append("WORKER_INACTIVE")
            if estimated_minutes is None:
                eligible = False
                reasons.append("DURATION_UNAVAILABLE")
            elif capacity is None or available_minutes <= 0:
                eligible = False
                reasons.append("NO_CAPACITY")
            elif available_minutes < estimated_minutes:
                eligible = False
                reasons.append("INSUFFICIENT_CAPACITY")
            elif not _has_contiguous_capacity(operation, capacity, estimated_minutes, as_of):
                eligible = False
                reasons.append("NO_CONTIGUOUS_SLOT")

            if eligible:
                reasons.append("ELIGIBLE")

            score = 0.0
            if applicable_weight > 0:
                score = min(100.0, 100.0 * weighted_score / applicable_weight)

            candidates.append(
                ExecutorCandidate(
                    operation_id=operation.operation_id,
                    worker_id=worker.worker_id,
                    score=round(score, 6),
                    eligible=eligible,
                    available_minutes=available_minutes,
                    reason_codes=tuple(reasons),
                )
            )

        candidates.sort(
            key=lambda candidate: (
                not candidate.eligible,
                -candidate.score,
                -candidate.available_minutes,
                candidate.worker_id,
            )
        )
        result[operation.operation_id] = tuple(candidates[: settings.top_n])

    return result


__all__ = ["suggest_executants"]
