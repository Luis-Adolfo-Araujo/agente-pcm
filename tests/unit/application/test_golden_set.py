from __future__ import annotations

import json
from datetime import UTC, datetime

from application.pilot.golden_set import golden_set_jsonl
from application.pilot.models import FeedbackRecord, FeedbackSkill, FeedbackVerdict


def _record(
    feedback_id: str,
    operation_id: str,
    skill: FeedbackSkill,
    verdict: FeedbackVerdict,
    minute: int,
) -> FeedbackRecord:
    return FeedbackRecord(
        feedback_id=feedback_id,
        run_id="run-1",
        snapshot_id="snapshot-1",
        operation_id=operation_id,
        skill=skill,
        verdict=verdict,
        reason="avaliado na sessão assistida",
        recorded_by="planejador-1",
        recorded_at=datetime(2026, 8, 18, 10, minute, tzinfo=UTC),
    )


def test_golden_set_writes_one_json_object_per_evaluation() -> None:
    text = golden_set_jsonl(
        (
            _record("f-1", "op-a", FeedbackSkill.RANKING, FeedbackVerdict.CORRECT, 1),
            _record("f-2", "op-b", FeedbackSkill.DURATION, FeedbackVerdict.INCORRECT, 2),
        )
    )

    lines = [json.loads(line) for line in text.splitlines()]
    assert len(lines) == 2
    assert lines[0]["snapshot_id"] == "snapshot-1"
    assert lines[0]["operation_id"] == "op-a"
    assert lines[0]["skill"] == "ranking"
    assert lines[0]["verdict"] == "correct"
    assert lines[0]["reason"] == "avaliado na sessão assistida"


def test_golden_set_is_deterministic_regardless_of_input_order() -> None:
    first = _record("f-1", "op-a", FeedbackSkill.RANKING, FeedbackVerdict.CORRECT, 1)
    second = _record("f-2", "op-b", FeedbackSkill.DURATION, FeedbackVerdict.INCORRECT, 2)

    assert golden_set_jsonl((first, second)) == golden_set_jsonl((second, first))


def test_golden_set_omits_the_evaluator_identity() -> None:
    text = golden_set_jsonl(
        (_record("f-1", "op-a", FeedbackSkill.RANKING, FeedbackVerdict.CORRECT, 1),)
    )

    payload = json.loads(text.splitlines()[0])
    assert "recorded_by" not in payload
    assert "planejador-1" not in text


def test_golden_set_of_an_empty_evaluation_is_an_empty_file() -> None:
    assert golden_set_jsonl(()) == ""
