"""Verificador independente das restrições duras de uma programação."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime

from domain.planning.entities import (
    EnrichedOperation,
    ExistingAssignment,
    PlanningRequest,
    PlanningSnapshot,
    SchedulingSolution,
    VerificationReport,
    VerificationViolation,
)
from domain.planning.enums import SolutionStatus, ViolationSeverity

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


def _normalize_status(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return "_".join(ascii_value.casefold().replace("-", " ").split())


def _has_non_plannable_status(status: str, planning_status: str) -> bool:
    return any(
        _normalize_status(value) in _NON_PLANNABLE_STATUSES
        for value in (status, planning_status)
        if value
    )


def _canonical_enriched(
    enriched: Mapping[str, EnrichedOperation] | Iterable[EnrichedOperation],
) -> tuple[EnrichedOperation, ...]:
    values = enriched.values() if isinstance(enriched, Mapping) else enriched
    return tuple(sorted(values, key=lambda item: item.operation.operation_id))


def _input_hash(
    solution: SchedulingSolution,
    snapshot: PlanningSnapshot,
    enriched: tuple[EnrichedOperation, ...],
    request: PlanningRequest,
) -> str:
    payload = {
        "solution": solution.model_dump(mode="json"),
        "snapshot": snapshot.model_dump(mode="json"),
        "enriched": [item.model_dump(mode="json") for item in enriched],
        "request": request.model_dump(mode="json"),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _overlaps(first: _Interval, second: _Interval) -> bool:
    return first[0] < second[1] and second[0] < first[1]


def _contains(intervals: Iterable[_Interval], target: _Interval) -> bool:
    start, end = target
    return any(
        interval_start <= start and end <= interval_end
        for interval_start, interval_end in intervals
    )


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


def _subtract(intervals: Iterable[_Interval], occupied: Iterable[_Interval]) -> list[_Interval]:
    remaining = _merge_intervals(intervals)
    for occupied_start, occupied_end in _merge_intervals(occupied):
        updated: list[_Interval] = []
        for start, end in remaining:
            if occupied_end <= start or end <= occupied_start:
                updated.append((start, end))
                continue
            if start < occupied_start:
                updated.append((start, occupied_start))
            if occupied_end < end:
                updated.append((occupied_end, end))
        remaining = updated
    return remaining


def _violation(
    code: str,
    details: str,
    *,
    operation_id: str | None = None,
    worker_id: str | None = None,
    repairable: bool = False,
    severity: ViolationSeverity = ViolationSeverity.ERROR,
) -> VerificationViolation:
    return VerificationViolation(
        code=code,
        severity=severity,
        operation_id=operation_id,
        worker_id=worker_id,
        details=details,
        repairable=repairable,
    )


def _existing_by_worker(
    assignments: Iterable[ExistingAssignment],
) -> dict[str, list[ExistingAssignment]]:
    result: dict[str, list[ExistingAssignment]] = defaultdict(list)
    for assignment in assignments:
        result[assignment.worker_id].append(assignment)
    for worker_assignments in result.values():
        worker_assignments.sort(
            key=lambda assignment: (
                assignment.window.start,
                assignment.window.end,
                assignment.operation_id,
            )
        )
    return result


def verify_schedule(
    solution: SchedulingSolution,
    snapshot: PlanningSnapshot,
    enriched: Mapping[str, EnrichedOperation] | Iterable[EnrichedOperation],
    request: PlanningRequest,
) -> VerificationReport:
    """Recalcula invariantes sem chamar ou confiar na heurística do otimizador."""

    enriched_items = _canonical_enriched(enriched)
    enriched_by_id = {item.operation.operation_id: item for item in enriched_items}
    snapshot_by_id = {operation.operation_id: operation for operation in snapshot.operations}
    workers_by_id = {worker.worker_id: worker for worker in snapshot.workers}
    existing_by_worker = _existing_by_worker(snapshot.existing_assignments)

    availability_by_worker: dict[str, list[_Interval]] = defaultdict(list)
    for slot in snapshot.availability:
        start = max(slot.window.start, request.period.start)
        end = min(slot.window.end, request.period.end)
        if end > start:
            availability_by_worker[slot.worker_id].append((start, end))
    availability_by_worker = {
        worker_id: _merge_intervals(intervals)
        for worker_id, intervals in availability_by_worker.items()
    }

    violations: list[VerificationViolation] = []
    if snapshot.tenant_id != request.tenant_id:
        violations.append(
            _violation(
                "TENANT_MISMATCH",
                "snapshot and planning request belong to different tenants",
            )
        )

    assigned_operation_ids: set[str] = set()
    assignments_by_worker: dict[str, list[tuple[str, _Interval]]] = defaultdict(list)

    for assignment in solution.assignments:
        operation_id = assignment.operation_id
        interval = (assignment.window.start, assignment.window.end)
        item = enriched_by_id.get(operation_id)
        operation = snapshot_by_id.get(operation_id)

        if operation_id in assigned_operation_ids:
            violations.append(
                _violation(
                    "DUPLICATE_OPERATION",
                    "operation appears in more than one assignment",
                    operation_id=operation_id,
                    repairable=True,
                )
            )
        assigned_operation_ids.add(operation_id)

        if operation is None:
            violations.append(
                _violation(
                    "UNKNOWN_OPERATION",
                    "assigned operation does not exist in the snapshot",
                    operation_id=operation_id,
                )
            )
            continue
        if item is None:
            violations.append(
                _violation(
                    "MISSING_ENRICHMENT",
                    "assigned operation has no enriched planning state",
                    operation_id=operation_id,
                )
            )
            continue

        if assignment.work_order_id != operation.work_order_id:
            violations.append(
                _violation(
                    "WORK_ORDER_MISMATCH",
                    "assignment references a work order different from the snapshot",
                    operation_id=operation_id,
                )
            )

        if not assignment.reason_codes:
            violations.append(
                _violation(
                    "MISSING_JUSTIFICATION",
                    "assignment has no structured reason code",
                    operation_id=operation_id,
                    repairable=True,
                )
            )

        if assignment.priority_score != item.priority.score:
            violations.append(
                _violation(
                    "PRIORITY_SCORE_MISMATCH",
                    "assignment priority differs from the enriched assessment",
                    operation_id=operation_id,
                    repairable=True,
                )
            )

        if (
            assignment.window.start < request.period.start
            or assignment.window.end > request.period.end
        ):
            violations.append(
                _violation(
                    "OUTSIDE_PERIOD",
                    "assignment is not fully contained in the requested period",
                    operation_id=operation_id,
                    repairable=True,
                )
            )

        if (
            assignment.window.start < request.as_of
            or assignment.window.start < operation.created_at
        ):
            violations.append(
                _violation(
                    "OPERATION_NOT_AVAILABLE",
                    "assignment starts before the operation is available for planning",
                    operation_id=operation_id,
                    repairable=True,
                )
            )

        if operation.operational_windows and not _contains(
            (
                (window.start, window.end)
                for window in operation.operational_windows
            ),
            interval,
        ):
            violations.append(
                _violation(
                    "OUTSIDE_OPERATIONAL_WINDOW",
                    "assignment is not contained in an operational window",
                    operation_id=operation_id,
                    repairable=True,
                )
            )

        if operation.blocked:
            violations.append(
                _violation(
                    "BLOCKED_OPERATION",
                    "blocked operation was assigned",
                    operation_id=operation_id,
                    repairable=True,
                )
            )

        if _has_non_plannable_status(operation.status, operation.planning_status):
            violations.append(
                _violation(
                    "NON_PLANNABLE_STATUS",
                    "operation status does not permit scheduling",
                    operation_id=operation_id,
                    repairable=True,
                )
            )

        if item.materials.blocking:
            violations.append(
                _violation(
                    "BLOCKING_MATERIAL",
                    "operation with blocking material assessment was assigned",
                    operation_id=operation_id,
                    repairable=True,
                )
            )

        if item.duration.minutes is None:
            violations.append(
                _violation(
                    "DURATION_UNAVAILABLE",
                    "operation without a duration estimate was assigned",
                    operation_id=operation_id,
                    repairable=True,
                )
            )
        elif assignment.window.minutes < item.duration.minutes:
            violations.append(
                _violation(
                    "INSUFFICIENT_DURATION",
                    "assignment is shorter than the estimated duration",
                    operation_id=operation_id,
                    repairable=True,
                )
            )

        unique_worker_ids = tuple(dict.fromkeys(assignment.worker_ids))
        if len(unique_worker_ids) != len(assignment.worker_ids):
            violations.append(
                _violation(
                    "DUPLICATE_EXECUTANT",
                    "the same worker appears more than once in the assignment",
                    operation_id=operation_id,
                    repairable=True,
                )
            )
        if len(unique_worker_ids) < operation.required_worker_count:
            violations.append(
                _violation(
                    "INSUFFICIENT_EXECUTANTS",
                    "assignment does not meet the required worker count",
                    operation_id=operation_id,
                    repairable=True,
                )
            )

        candidate_by_worker = {candidate.worker_id: candidate for candidate in item.executants}
        for worker_id in unique_worker_ids:
            worker = workers_by_id.get(worker_id)
            if worker is None or not worker.active:
                violations.append(
                    _violation(
                        "INACTIVE_OR_UNKNOWN_EXECUTANT",
                        "assigned worker is unknown or inactive",
                        operation_id=operation_id,
                        worker_id=worker_id,
                        repairable=True,
                    )
                )

            candidate = candidate_by_worker.get(worker_id)
            if candidate is None or not candidate.eligible:
                violations.append(
                    _violation(
                        "INELIGIBLE_EXECUTANT",
                        "assigned worker is not an eligible candidate",
                        operation_id=operation_id,
                        worker_id=worker_id,
                        repairable=True,
                    )
                )

            availability = availability_by_worker.get(worker_id, [])
            if not _contains(availability, interval):
                violations.append(
                    _violation(
                        "OUTSIDE_AVAILABILITY",
                        "assignment is not contained in worker availability",
                        operation_id=operation_id,
                        worker_id=worker_id,
                        repairable=True,
                    )
                )

            for existing in existing_by_worker.get(worker_id, []):
                if _overlaps(interval, (existing.window.start, existing.window.end)):
                    violations.append(
                        _violation(
                            "EXISTING_ASSIGNMENT_CONFLICT",
                            f"assignment overlaps existing operation {existing.operation_id}",
                            operation_id=operation_id,
                            worker_id=worker_id,
                            repairable=True,
                        )
                    )
                    break

            assignments_by_worker[worker_id].append((operation_id, interval))

    for worker_id in sorted(assignments_by_worker):
        worker_assignments = sorted(
            assignments_by_worker[worker_id],
            key=lambda value: (value[1][0], value[1][1], value[0]),
        )
        for index, (operation_id, interval) in enumerate(worker_assignments):
            for other_operation_id, other_interval in worker_assignments[index + 1 :]:
                if other_interval[0] >= interval[1]:
                    break
                if _overlaps(interval, other_interval):
                    violations.append(
                        _violation(
                            "WORKER_OVERLAP",
                            f"worker is also assigned to operation {other_operation_id}",
                            operation_id=operation_id,
                            worker_id=worker_id,
                            repairable=True,
                        )
                    )

        occupied = [
            (assignment.window.start, assignment.window.end)
            for assignment in existing_by_worker.get(worker_id, [])
        ]
        free_capacity = _subtract(availability_by_worker.get(worker_id, []), occupied)
        free_minutes = sum(int((end - start).total_seconds() // 60) for start, end in free_capacity)
        assigned_minutes = sum(
            int((end - start).total_seconds() // 60)
            for _, (start, end) in worker_assignments
        )
        if assigned_minutes > free_minutes:
            violations.append(
                _violation(
                    "CAPACITY_EXCEEDED",
                    "total assigned minutes exceed the worker's net capacity",
                    worker_id=worker_id,
                    repairable=True,
                )
            )

    unscheduled_ids: set[str] = set()
    for unscheduled_operation in solution.unscheduled:
        if unscheduled_operation.operation_id in unscheduled_ids:
            violations.append(
                _violation(
                    "DUPLICATE_UNSCHEDULED_OPERATION",
                    "operation appears more than once in the unscheduled list",
                    operation_id=unscheduled_operation.operation_id,
                    repairable=True,
                )
            )
        unscheduled_ids.add(unscheduled_operation.operation_id)

        if unscheduled_operation.operation_id not in snapshot_by_id:
            violations.append(
                _violation(
                    "UNKNOWN_UNSCHEDULED_OPERATION",
                    "unscheduled operation does not exist in the snapshot",
                    operation_id=unscheduled_operation.operation_id,
                )
            )
        if unscheduled_operation.operation_id in assigned_operation_ids:
            violations.append(
                _violation(
                    "ASSIGNED_AND_UNSCHEDULED",
                    "operation appears as both assigned and unscheduled",
                    operation_id=unscheduled_operation.operation_id,
                    repairable=True,
                )
            )

    represented = assigned_operation_ids | unscheduled_ids
    for operation_id in sorted(set(enriched_by_id) - represented):
        violations.append(
            _violation(
                "MISSING_OPERATION_RESULT",
                "enriched operation is absent from the solution",
                operation_id=operation_id,
                repairable=True,
            )
        )

    if not solution.unscheduled:
        expected_status = SolutionStatus.FEASIBLE
    elif solution.assignments:
        expected_status = SolutionStatus.PARTIAL
    else:
        expected_status = SolutionStatus.INFEASIBLE
    if solution.status != expected_status:
        violations.append(
            _violation(
                "SOLUTION_STATUS_MISMATCH",
                f"solution status should be {expected_status.value}",
                repairable=True,
            )
        )

    valid = not any(violation.severity == ViolationSeverity.ERROR for violation in violations)
    return VerificationReport(
        valid=valid,
        input_hash=_input_hash(solution, snapshot, enriched_items, request),
        violations=tuple(violations),
    )


__all__ = ["verify_schedule"]
