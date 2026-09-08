"""Baseline guloso, estável e auditável para programação de manutenção."""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta

from domain.planning.config import OptimizerConfig, PlanningConfig
from domain.planning.entities import (
    CapacityAssessment,
    EnrichedOperation,
    ExecutorCandidate,
    PlanningRequest,
    ScheduleAssignment,
    SchedulingSolution,
    TimeWindow,
    UnscheduledOperation,
    WorkOrderOperation,
)
from domain.planning.enums import SolutionStatus, UnscheduledReason

_Interval = tuple[datetime, datetime]

_NON_PLANNABLE_STATUSES = frozenset(
    {
        "archived",
        "cancelada",
        "cancelado",
        "canceled",
        "cancelled",
        "closed",
        "completed",
        "concluida",
        "concluido",
        "deleted",
        "em_espera",
        "excluded",
        "excluida",
        "excluido",
        "fechada",
        "fechado",
        "finished",
        "on_hold",
        "waiting",
    }
)


def _optimizer_config(config: OptimizerConfig | PlanningConfig) -> OptimizerConfig:
    return config.optimizer if isinstance(config, PlanningConfig) else config


def _normalize_status(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return "_".join(ascii_value.casefold().replace("-", " ").split())


def _is_non_plannable(operation: WorkOrderOperation) -> bool:
    return any(
        _normalize_status(value) in _NON_PLANNABLE_STATUSES
        for value in (operation.status, operation.planning_status)
        if value
    )


def _capacity_values(
    capacities: Mapping[str, CapacityAssessment] | Iterable[CapacityAssessment],
) -> tuple[CapacityAssessment, ...]:
    values = capacities.values() if isinstance(capacities, Mapping) else capacities
    return tuple(values)


def _merge_intervals(intervals: Iterable[_Interval]) -> list[_Interval]:
    ordered = sorted(
        ((start, end) for start, end in intervals if end > start),
        key=lambda interval: (interval[0], interval[1]),
    )
    merged: list[_Interval] = []
    for start, end in ordered:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
            continue
        previous_start, previous_end = merged[-1]
        merged[-1] = (previous_start, max(previous_end, end))
    return merged


def _initial_free_slots(
    capacities: Mapping[str, CapacityAssessment] | Iterable[CapacityAssessment],
    period: TimeWindow,
) -> dict[str, list[_Interval]]:
    intervals_by_worker: dict[str, list[_Interval]] = {}
    for capacity in _capacity_values(capacities):
        intervals = intervals_by_worker.setdefault(capacity.worker_id, [])
        for slot in capacity.slots:
            if slot.worker_id != capacity.worker_id:
                continue
            start = max(slot.window.start, period.start)
            end = min(slot.window.end, period.end)
            if end > start:
                intervals.append((start, end))
    return {
        worker_id: _merge_intervals(intervals)
        for worker_id, intervals in intervals_by_worker.items()
    }


def _operation_windows(operation: WorkOrderOperation, request: PlanningRequest) -> list[_Interval]:
    earliest_start = max(request.period.start, request.as_of, operation.created_at)
    if earliest_start >= request.period.end:
        return []

    if not operation.operational_windows:
        return [(earliest_start, request.period.end)]

    intersections: list[_Interval] = []
    for operational_window in operation.operational_windows:
        start = max(earliest_start, operational_window.start)
        end = min(request.period.end, operational_window.end)
        if end > start:
            intersections.append((start, end))
    return _merge_intervals(intersections)


def _align_up(value: datetime, origin: datetime, granularity_minutes: int) -> datetime:
    granularity_seconds = granularity_minutes * 60
    elapsed_seconds = (value - origin).total_seconds()
    steps = math.ceil(elapsed_seconds / granularity_seconds)
    return origin + timedelta(seconds=steps * granularity_seconds)


def _contains(intervals: Iterable[_Interval], start: datetime, end: datetime) -> bool:
    return any(
        interval_start <= start and end <= interval_end
        for interval_start, interval_end in intervals
    )


def _candidate_key(candidate: ExecutorCandidate) -> tuple[float, int, str]:
    return (-candidate.score, -candidate.available_minutes, candidate.worker_id)


def _find_assignment(
    candidates: list[ExecutorCandidate],
    required_worker_count: int,
    duration_minutes: int,
    allowed_windows: list[_Interval],
    free_slots: dict[str, list[_Interval]],
    request: PlanningRequest,
    granularity_minutes: int,
) -> tuple[tuple[str, ...], datetime, datetime] | None:
    candidates = sorted(candidates, key=_candidate_key)
    duration = timedelta(minutes=duration_minutes)

    # O início de toda interseção factível coincide com o início de uma
    # janela operacional ou de um slot livre. Avaliar esses limites evita uma
    # enumeração combinatória de grupos de executantes.
    possible_starts = {start for start, _ in allowed_windows}
    for candidate in candidates:
        possible_starts.update(start for start, _ in free_slots.get(candidate.worker_id, []))

    choices: list[tuple[float, datetime, tuple[str, ...], datetime]] = []
    for boundary in sorted(possible_starts):
        start = _align_up(boundary, request.period.start, granularity_minutes)
        end = start + duration
        if not _contains(allowed_windows, start, end):
            continue

        available = [
            candidate
            for candidate in candidates
            if _contains(free_slots.get(candidate.worker_id, ()), start, end)
        ]
        if len(available) < required_worker_count:
            continue

        selected = tuple(sorted(available[:required_worker_count], key=_candidate_key))
        worker_ids = tuple(sorted(candidate.worker_id for candidate in selected))
        total_score = sum(candidate.score for candidate in selected)
        choices.append((-total_score, start, worker_ids, end))

    if not choices:
        return None
    _, start, worker_ids, end = min(choices, key=lambda choice: choice[:3])
    return worker_ids, start, end


def _consume_slot(
    free_slots: dict[str, list[_Interval]], worker_id: str, start: datetime, end: datetime
) -> None:
    remaining: list[_Interval] = []
    for interval_start, interval_end in free_slots.get(worker_id, []):
        if end <= interval_start or interval_end <= start:
            remaining.append((interval_start, interval_end))
            continue
        if interval_start < start:
            remaining.append((interval_start, start))
        if end < interval_end:
            remaining.append((end, interval_end))
    free_slots[worker_id] = remaining


def _unscheduled(
    enriched: EnrichedOperation,
    reason: UnscheduledReason,
    *details: str,
) -> UnscheduledOperation:
    return UnscheduledOperation(
        work_order_id=enriched.operation.work_order_id,
        operation_id=enriched.operation.operation_id,
        reason=reason,
        details=tuple(detail for detail in details if detail),
    )


def _canonical_enriched(
    enriched: Mapping[str, EnrichedOperation] | Iterable[EnrichedOperation],
) -> tuple[EnrichedOperation, ...]:
    values = enriched.values() if isinstance(enriched, Mapping) else enriched
    by_operation: dict[str, EnrichedOperation] = {}
    for item in values:
        by_operation.setdefault(item.operation.operation_id, item)
    return tuple(by_operation.values())


def optimize_schedule(
    enriched: Mapping[str, EnrichedOperation] | Iterable[EnrichedOperation],
    capacities: Mapping[str, CapacityAssessment] | Iterable[CapacityAssessment],
    request: PlanningRequest,
    config: OptimizerConfig | PlanningConfig,
) -> SchedulingSolution:
    """Gera uma solução gulosa priorizando operações de maior score.

    A heurística escolhe, para cada operação, o grupo elegível com maior
    compatibilidade que compartilha um slot contíguo. Empates são resolvidos
    por data e IDs, garantindo replay bit a bit para a mesma entrada.
    """

    settings = _optimizer_config(config)
    free_slots = _initial_free_slots(capacities, request.period)
    assignments: list[ScheduleAssignment] = []
    unscheduled: list[UnscheduledOperation] = []

    ordered = sorted(
        _canonical_enriched(enriched),
        key=lambda item: (
            -item.priority.score,
            item.operation.due_at is None,
            item.operation.due_at or request.period.end,
            item.operation.created_at,
            item.operation.operation_id,
        ),
    )

    for item in ordered:
        operation = item.operation
        if operation.blocked or _is_non_plannable(operation):
            unscheduled.append(
                _unscheduled(
                    item,
                    UnscheduledReason.BLOCKED,
                    operation.block_reason or "OPERATION_BLOCKED",
                )
            )
            continue

        if item.materials.blocking:
            unscheduled.append(
                _unscheduled(item, UnscheduledReason.MATERIAL, *item.materials.reason_codes)
            )
            continue

        if item.duration.minutes is None:
            unscheduled.append(
                _unscheduled(item, UnscheduledReason.DURATION, *item.duration.reason_codes)
            )
            continue

        allowed_windows = _operation_windows(operation, request)
        if not allowed_windows:
            reason = (
                UnscheduledReason.OUTSIDE_WINDOW
                if operation.operational_windows
                else UnscheduledReason.OUTSIDE_PERIOD
            )
            unscheduled.append(_unscheduled(item, reason, "NO_ALLOWED_WINDOW_IN_PERIOD"))
            continue

        eligible_candidates = [
            candidate
            for candidate in item.executants
            if candidate.eligible and candidate.worker_id in free_slots
        ]
        if len(eligible_candidates) < operation.required_worker_count:
            capacity_codes = {"NO_CAPACITY", "INSUFFICIENT_CAPACITY", "NO_CONTIGUOUS_SLOT"}
            capacity_limited = any(
                capacity_codes.intersection(candidate.reason_codes)
                for candidate in item.executants
            ) or any(
                candidate.eligible and candidate.worker_id not in free_slots
                for candidate in item.executants
            )
            unscheduled.append(
                _unscheduled(
                    item,
                    UnscheduledReason.NO_CAPACITY
                    if capacity_limited
                    else UnscheduledReason.NO_EXECUTANT,
                    "INSUFFICIENT_ELIGIBLE_EXECUTANTS",
                )
            )
            continue

        found = _find_assignment(
            eligible_candidates,
            operation.required_worker_count,
            item.duration.minutes,
            allowed_windows,
            free_slots,
            request,
            settings.slot_granularity_minutes,
        )
        if found is None:
            unscheduled.append(
                _unscheduled(item, UnscheduledReason.NO_CAPACITY, "NO_SHARED_CONTIGUOUS_SLOT")
            )
            continue

        worker_ids, start, end = found
        for worker_id in worker_ids:
            _consume_slot(free_slots, worker_id, start, end)

        reason_codes = ["PRIORITY_ORDER", "EXECUTANT_SCORE", "EARLIEST_FEASIBLE_SLOT"]
        if operation.required_worker_count > 1:
            reason_codes.append("MULTIPLE_EXECUTANTS")
        assignments.append(
            ScheduleAssignment(
                work_order_id=operation.work_order_id,
                operation_id=operation.operation_id,
                worker_ids=worker_ids,
                window=TimeWindow(start=start, end=end),
                priority_score=item.priority.score,
                reason_codes=tuple(reason_codes),
            )
        )

    if not unscheduled:
        status = SolutionStatus.FEASIBLE
    elif assignments:
        status = SolutionStatus.PARTIAL
    else:
        status = SolutionStatus.INFEASIBLE

    return SchedulingSolution(
        status=status,
        assignments=tuple(assignments),
        unscheduled=tuple(unscheduled),
        objective_value=round(sum(assignment.priority_score for assignment in assignments), 6),
        algorithm_version=settings.algorithm_version,
    )


__all__ = ["optimize_schedule"]
