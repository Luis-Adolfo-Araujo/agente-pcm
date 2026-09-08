"""Cálculo determinístico de capacidade líquida por executante."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import tzinfo

from domain.planning.entities import (
    AvailabilitySlot,
    CapacityAssessment,
    CapacitySlot,
    ExistingAssignment,
    TimeWindow,
    WorkerProfile,
)


def calculate_capacity(
    workers: Sequence[WorkerProfile],
    availability: Sequence[AvailabilitySlot],
    existing_assignments: Sequence[ExistingAssignment],
    period: TimeWindow,
) -> tuple[CapacityAssessment, ...]:
    """Calcula capacidade bruta, comprometida e livre dentro de ``period``.

    Intervalos sobrepostos são unidos antes do cálculo. Compromissos só
    consomem a parte que intersecta a disponibilidade conhecida do executante.
    Assim, dados duplicados não contam duas vezes e a capacidade nunca é negativa.
    """

    active_worker_ids = sorted({worker.worker_id for worker in workers if worker.active})
    availability_by_worker: dict[str, list[TimeWindow]] = defaultdict(list)
    assignments_by_worker: dict[str, list[TimeWindow]] = defaultdict(list)

    active_worker_id_set = set(active_worker_ids)
    for slot in availability:
        if slot.worker_id in active_worker_id_set:
            clipped = _clip(slot.window, period)
            if clipped is not None:
                availability_by_worker[slot.worker_id].append(clipped)

    for assignment in existing_assignments:
        if assignment.worker_id in active_worker_id_set:
            clipped = _clip(assignment.window, period)
            if clipped is not None:
                assignments_by_worker[assignment.worker_id].append(clipped)

    assessments: list[CapacityAssessment] = []
    output_timezone = period.start.tzinfo
    assert output_timezone is not None  # TimeWindow already validates this invariant.

    for worker_id in active_worker_ids:
        gross_windows = _merge(availability_by_worker[worker_id], output_timezone)
        assignment_windows = _merge(assignments_by_worker[worker_id], output_timezone)
        committed_windows = _intersections(gross_windows, assignment_windows)
        free_windows = _subtract(gross_windows, assignment_windows)

        gross_minutes = _total_minutes(gross_windows)
        committed_minutes = min(gross_minutes, _total_minutes(committed_windows))
        net_minutes = max(0, gross_minutes - committed_minutes)

        assessments.append(
            CapacityAssessment(
                worker_id=worker_id,
                gross_minutes=gross_minutes,
                committed_minutes=committed_minutes,
                net_minutes=net_minutes,
                slots=tuple(
                    CapacitySlot(worker_id=worker_id, window=window) for window in free_windows
                ),
            )
        )

    return tuple(assessments)


def _clip(window: TimeWindow, period: TimeWindow) -> TimeWindow | None:
    start = max(window.start, period.start)
    end = min(window.end, period.end)
    if end <= start:
        return None
    return TimeWindow(start=start, end=end)


def _merge(windows: Iterable[TimeWindow], timezone: tzinfo) -> tuple[TimeWindow, ...]:
    ordered = sorted(
        (
            TimeWindow(
                start=window.start.astimezone(timezone),
                end=window.end.astimezone(timezone),
            )
            for window in windows
        ),
        key=lambda window: (window.start, window.end),
    )
    if not ordered:
        return ()

    merged: list[TimeWindow] = []
    current_start = ordered[0].start
    current_end = ordered[0].end
    for window in ordered[1:]:
        if window.start <= current_end:
            current_end = max(current_end, window.end)
            continue
        merged.append(TimeWindow(start=current_start, end=current_end))
        current_start = window.start
        current_end = window.end
    merged.append(TimeWindow(start=current_start, end=current_end))
    return tuple(merged)


def _intersections(
    left: Sequence[TimeWindow], right: Sequence[TimeWindow]
) -> tuple[TimeWindow, ...]:
    intersections: list[TimeWindow] = []
    left_index = 0
    right_index = 0
    while left_index < len(left) and right_index < len(right):
        left_window = left[left_index]
        right_window = right[right_index]
        start = max(left_window.start, right_window.start)
        end = min(left_window.end, right_window.end)
        if start < end:
            intersections.append(TimeWindow(start=start, end=end))

        if left_window.end <= right_window.end:
            left_index += 1
        else:
            right_index += 1
    return tuple(intersections)


def _subtract(
    available: Sequence[TimeWindow], assignments: Sequence[TimeWindow]
) -> tuple[TimeWindow, ...]:
    free: list[TimeWindow] = []
    for available_window in available:
        cursor = available_window.start
        for assignment in assignments:
            if assignment.end <= cursor:
                continue
            if assignment.start >= available_window.end:
                break

            if assignment.start > cursor:
                free.append(
                    TimeWindow(start=cursor, end=min(assignment.start, available_window.end))
                )
            cursor = max(cursor, assignment.end)
            if cursor >= available_window.end:
                break

        if cursor < available_window.end:
            free.append(TimeWindow(start=cursor, end=available_window.end))

    return tuple(free)


def _total_minutes(windows: Iterable[TimeWindow]) -> int:
    total_seconds = sum((window.end - window.start).total_seconds() for window in windows)
    return int(total_seconds // 60)
