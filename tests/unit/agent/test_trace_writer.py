import json
from pathlib import Path

import pytest

from agent.trace.writer import PlanningTraceRecorder, write_trace_jsonl
from domain.planning.entities import PlanningStageTrace


def test_recorder_emits_stable_sequence_counts_and_elapsed_time() -> None:
    ticks = iter((1_000_000, 2_500_000, 5_000_000, 5_250_000))
    recorder = PlanningTraceRecorder(clock_ns=lambda: next(ticks))

    first_started = recorder.start()
    first = recorder.complete(
        "skills_parallel",
        first_started,
        counts={"priorities": 2, "durations": 2},
    )
    second_started = recorder.start()
    second = recorder.complete("verification", second_started, counts={"violations": 0})

    assert first.sequence == 1
    assert first.elapsed_ms == 1.5
    assert tuple(first.counts) == ("durations", "priorities")
    assert second.sequence == 2
    assert second.elapsed_ms == 0.25
    assert recorder.events == (first, second)


def test_recorder_rejects_invalid_counts() -> None:
    recorder = PlanningTraceRecorder(clock_ns=lambda: 1)

    with pytest.raises(ValueError, match="non-negative integers"):
        recorder.complete("invalid", 0, counts={"records": -1})


def test_recorder_notifies_listener_after_persisting_event() -> None:
    observed: list[PlanningStageTrace] = []
    recorder = PlanningTraceRecorder(clock_ns=lambda: 1, listener=observed.append)

    event = recorder.complete("snapshot_validated", 1, counts={"operations": 2})

    assert observed == [event]
    assert recorder.events == (event,)


def test_writer_keeps_stage_events_and_backwards_compatible_completion(tmp_path: Path) -> None:
    recorder = PlanningTraceRecorder(clock_ns=lambda: 1)
    recorder.complete("snapshot_validated", 1, counts={"operations": 2})
    path = tmp_path / "trace.jsonl"

    write_trace_jsonl(
        path,
        recorder.events,
        completion_event={"event": "planning_run_completed", "proposal_id": "proposal-1"},
    )

    payloads = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert payloads == [
        {
            "counts": {"operations": 2},
            "elapsed_ms": 0.0,
            "event": "planning_stage_completed",
            "sequence": 1,
            "stage": "snapshot_validated",
        },
        {"event": "planning_run_completed", "proposal_id": "proposal-1"},
    ]
    assert not path.with_suffix(".jsonl.tmp").exists()
