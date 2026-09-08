from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from application.cli import main
from application.pilot.models import (
    FeedbackRecord,
    FeedbackSkill,
    FeedbackVerdict,
    PilotRun,
    RunStatus,
)
from application.pilot.store import SQLitePilotStore
from domain.planning.config import PlanningConfig
from domain.planning.entities import PlanningRequest, TimeWindow

AS_OF = datetime(2026, 8, 17, 12, tzinfo=UTC)
PERIOD = TimeWindow(
    start=datetime(2026, 8, 18, tzinfo=UTC),
    end=datetime(2026, 8, 25, tzinfo=UTC),
)


def _seeded_database(tmp_path: Path) -> Path:
    db_path = tmp_path / "pilot.sqlite3"
    store = SQLitePilotStore(db_path)
    store.initialize()
    store.create_run(
        PilotRun(
            run_id="run-1",
            snapshot_id="snapshot-1",
            tenant_id="planta-modelo",
            status=RunStatus.QUEUED,
            created_at=AS_OF,
            request=PlanningRequest(tenant_id="planta-modelo", period=PERIOD, as_of=AS_OF),
            config=PlanningConfig(),
        )
    )
    store.add_feedback(
        (
            FeedbackRecord(
                feedback_id="f-1",
                run_id="run-1",
                snapshot_id="snapshot-1",
                operation_id="op-a",
                skill=FeedbackSkill.RANKING,
                verdict=FeedbackVerdict.ACCEPTABLE,
                reason="ordem aceitável para a semana",
                recorded_by="planejador-1",
                recorded_at=AS_OF,
            ),
        )
    )
    return db_path


def test_cli_exports_the_collected_feedback_as_a_golden_set(tmp_path: Path) -> None:
    db_path = _seeded_database(tmp_path)
    target = tmp_path / "datasets" / "golden-set.jsonl"

    exit_code = main(
        [
            "export-golden-set",
            "--db",
            str(db_path),
            "--output",
            str(target),
        ]
    )

    assert exit_code == 0
    payload = json.loads(target.read_text(encoding="utf-8").splitlines()[0])
    assert payload["operation_id"] == "op-a"
    assert payload["verdict"] == "acceptable"
    assert "recorded_by" not in payload
