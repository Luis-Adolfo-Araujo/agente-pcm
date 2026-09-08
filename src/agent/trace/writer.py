"""Small, deterministic-schema trace recorder and JSONL writer."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from domain.planning.entities import PlanningStageTrace


class PlanningTraceRecorder:
    """Collect completed planning stages in a stable sequence."""

    def __init__(
        self,
        clock_ns: Callable[[], int] = time.perf_counter_ns,
        listener: Callable[[PlanningStageTrace], None] | None = None,
    ) -> None:
        self._clock_ns = clock_ns
        self._listener = listener
        self._events: list[PlanningStageTrace] = []

    def start(self) -> int:
        """Capture a monotonic stage start marker."""

        return self._clock_ns()

    def complete(
        self,
        stage: str,
        started_ns: int,
        *,
        counts: Mapping[str, int] | None = None,
    ) -> PlanningStageTrace:
        """Record one completed stage with sorted, non-negative counters."""

        elapsed_ms = round(max(0, self._clock_ns() - started_ns) / 1_000_000, 3)
        return self.record(stage, elapsed_ms, counts=counts)

    def record(
        self,
        stage: str,
        elapsed_ms: float,
        *,
        counts: Mapping[str, int] | None = None,
    ) -> PlanningStageTrace:
        """Record a stage cronometrado em outro lugar.

        As skills paralelas medem o próprio tempo dentro da thread; o relógio do
        recorder mediria a soma da janela, não cada uma.
        """

        normalized_counts = dict(sorted((counts or {}).items()))
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in normalized_counts.values()
        ):
            raise ValueError("trace counts must be non-negative integers")
        event = PlanningStageTrace(
            sequence=len(self._events) + 1,
            stage=stage,
            elapsed_ms=round(max(0.0, elapsed_ms), 3),
            counts=normalized_counts,
        )
        self._events.append(event)
        if self._listener is not None:
            self._listener(event)
        return event

    @property
    def events(self) -> tuple[PlanningStageTrace, ...]:
        return tuple(self._events)


def write_trace_jsonl(
    path: Path,
    events: Iterable[PlanningStageTrace],
    *,
    completion_event: Mapping[str, Any] | None = None,
) -> None:
    """Atomically persist stage events and an optional backwards-compatible final event."""

    lines: list[str] = []
    for event in events:
        payload: dict[str, Any] = {
            "event": "planning_stage_completed",
            **event.model_dump(mode="json"),
        }
        lines.append(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        )
    if completion_event is not None:
        lines.append(
            json.dumps(
                dict(completion_event),
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    temporary.replace(path)
