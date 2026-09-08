from __future__ import annotations

import asyncio
import csv
import io
import json
from datetime import UTC, datetime

from application.pilot.exports import csv_export, json_export, run_summary
from application.pilot.models import PilotRun, RunStatus
from application.workflows.generate_schedule import generate_schedule
from domain.planning.config import PlanningConfig
from domain.planning.entities import (
    AvailabilitySlot,
    PlanningRequest,
    PlanningRunResult,
    PlanningSnapshot,
    TimeWindow,
    WorkerProfile,
    WorkOrderOperation,
)

AS_OF = datetime(2026, 8, 17, 12, tzinfo=UTC)
PERIOD = TimeWindow(
    start=datetime(2026, 8, 18, 8, tzinfo=UTC),
    end=datetime(2026, 8, 18, 17, tzinfo=UTC),
)


def _result(title: str = "Trocar rolamento") -> PlanningRunResult:
    snapshot = PlanningSnapshot(
        snapshot_id="snap-1",
        tenant_id="planta-modelo",
        as_of=AS_OF,
        operations=(
            WorkOrderOperation(
                work_order_id="wo-1",
                operation_id="op-1",
                title=title,
                status="open",
                created_at=datetime(2026, 8, 1, tzinfo=UTC),
                due_at=datetime(2026, 8, 20, tzinfo=UTC),
                priority_level=1,
                asset_id="asset-1",
                planned_duration_minutes=60,
            ),
        ),
        workers=(WorkerProfile(worker_id="worker-1"),),
        availability=(AvailabilitySlot(worker_id="worker-1", window=PERIOD),),
    )
    request = PlanningRequest(tenant_id="planta-modelo", period=PERIOD, as_of=AS_OF)
    return asyncio.run(generate_schedule(request, snapshot, PlanningConfig()))


def _run() -> PilotRun:
    return PilotRun(
        run_id="run-1",
        snapshot_id="snap-1",
        tenant_id="planta-modelo",
        status=RunStatus.QUEUED,
        created_at=AS_OF,
        request=PlanningRequest(tenant_id="planta-modelo", period=PERIOD, as_of=AS_OF),
        config=PlanningConfig(),
    )


def test_summary_counts_the_solution_and_the_verification() -> None:
    summary = run_summary(_result())

    assert summary.assignments == 1
    assert summary.unscheduled == 0
    assert summary.violations == 0
    assert summary.verification_valid is True
    assert summary.trace_elapsed_ms > 0


def test_json_export_carries_every_auditable_artifact() -> None:
    bundle = json_export(_run(), _result())

    assert set(bundle.files) == {
        "run.json",
        "request.json",
        "config.json",
        "result.json",
        "proposal.json",
        "verification.json",
        "enrichment.json",
        "summary.json",
        "trace.jsonl",
    }
    assert bundle.media_types["trace.jsonl"] == "application/x-ndjson"


def test_result_json_round_trips_back_into_the_domain_model() -> None:
    bundle = json_export(_run(), _result())

    restored = PlanningRunResult.model_validate_json(bundle.files["result.json"])

    assert len(restored.enriched) == 1
    assert restored.enriched[0].executants


def test_trace_jsonl_ends_with_the_run_completion_event() -> None:
    bundle = json_export(_run(), _result())

    events = [json.loads(line) for line in bundle.files["trace.jsonl"].splitlines()]

    assert events[-1]["event"] == "planning_run_completed"
    assert events[0]["stage"] == "snapshot_validated"


def test_csv_export_has_the_three_planned_files() -> None:
    bundle = csv_export(_run(), _result())

    assert set(bundle.files) == {"ranking.csv", "schedule.csv", "unscheduled.csv"}


def test_ranking_csv_decomposes_the_score_into_its_parcels() -> None:
    bundle = csv_export(_run(), _result())

    rows = list(csv.DictReader(io.StringIO(bundle.files["ranking.csv"])))

    assert len(rows) == 1
    assert rows[0]["operation_id"] == "op-1"
    assert rows[0]["position"] == "1"
    assert float(rows[0]["sla_contribution"]) >= 0
    assert rows[0]["duration_source"] == "planned"


def test_ranking_csv_neutralizes_a_formula_injected_through_a_title() -> None:
    bundle = csv_export(_run(), _result(title="=SOMA(A1:A9)"))

    rows = list(csv.DictReader(io.StringIO(bundle.files["ranking.csv"])))

    assert rows[0]["title"].startswith("'=")


def test_schedule_csv_reports_the_window_of_each_assignment() -> None:
    bundle = csv_export(_run(), _result())

    rows = list(csv.DictReader(io.StringIO(bundle.files["schedule.csv"])))

    assert rows[0]["worker_ids"] == "worker-1"
    assert rows[0]["duration_minutes"] == "60"
