from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from application.cli import main
from application.config import derive_weights_version
from application.workflows.generate_schedule import generate_schedule
from domain.planning.config import PlanningConfig
from domain.planning.entities import (
    AvailabilitySlot,
    HistoricalExecution,
    InventoryPosition,
    MaterialRequirement,
    PlanningRequest,
    PlanningSnapshot,
    TimeWindow,
    WorkerProfile,
    WorkOrderOperation,
)
from domain.planning.enums import ProposalStatus

AS_OF = datetime(2026, 8, 17, 12, tzinfo=UTC)
PERIOD = TimeWindow(
    start=datetime(2026, 8, 18, 8, tzinfo=UTC),
    end=datetime(2026, 8, 18, 17, tzinfo=UTC),
)


def _snapshot() -> PlanningSnapshot:
    operations = (
        WorkOrderOperation(
            work_order_id="wo-high",
            operation_id="op-high",
            title="Inspecionar redutor",
            status="open",
            planning_status="unplanned",
            created_at=datetime(2026, 7, 1, tzinfo=UTC),
            due_at=datetime(2026, 8, 16, tzinfo=UTC),
            priority_level=1,
            asset_id="asset-1",
            planned_team_id="mechanical",
            planned_duration_minutes=60,
        ),
        WorkOrderOperation(
            work_order_id="wo-medium",
            operation_id="op-medium",
            title="Trocar rolamento",
            status="open",
            planning_status="without_planning",
            created_at=datetime(2026, 8, 1, tzinfo=UTC),
            due_at=datetime(2026, 8, 25, tzinfo=UTC),
            priority_level=3,
            asset_id="asset-1",
            planned_team_id="mechanical",
            planned_duration_minutes=120,
            required_materials=(MaterialRequirement(item_id="bearing", quantity=1),),
        ),
    )
    return PlanningSnapshot(
        snapshot_id="fixture-1",
        tenant_id="planta-modelo",
        as_of=AS_OF,
        operations=operations,
        inventory=(InventoryPosition(item_id="bearing", on_hand_quantity=2),),
        workers=(
            WorkerProfile(worker_id="worker-1", team_ids=("mechanical",)),
            WorkerProfile(worker_id="worker-2", team_ids=("mechanical",)),
        ),
        availability=(
            AvailabilitySlot(worker_id="worker-1", window=PERIOD),
            AvailabilitySlot(worker_id="worker-2", window=PERIOD),
        ),
        history=(
            HistoricalExecution(
                work_order_id="wo-old",
                operation_id="op-old",
                title="Inspecionar redutor",
                finished_at=datetime(2026, 8, 1, tzinfo=UTC),
                duration_minutes=55,
                worker_ids=("worker-1",),
                asset_id="asset-1",
                team_id="mechanical",
            ),
        ),
    )


def _request() -> PlanningRequest:
    return PlanningRequest(tenant_id="planta-modelo", period=PERIOD, as_of=AS_OF)


def test_complete_workflow_is_valid_and_reproducible() -> None:
    first = asyncio.run(generate_schedule(_request(), _snapshot(), PlanningConfig()))
    second = asyncio.run(generate_schedule(_request(), _snapshot(), PlanningConfig()))

    assert first.proposal.status is ProposalStatus.DRAFT
    assert first.proposal.verification.valid
    assert len(first.proposal.solution.assignments) == 2
    assert not first.proposal.solution.unscheduled
    assert first.proposal.proposal_id == second.proposal.proposal_id
    assert first.proposal.solution == second.proposal.solution
    assert {item.operation_id for item in first.priorities} == {"op-high", "op-medium"}
    assert {item.operation.operation_id for item in first.enriched} == {
        "op-high",
        "op-medium",
    }
    assert [event.stage for event in first.trace_events] == [
        "snapshot_validated",
        "skill.rank_backlog",
        "skill.estimate_duration",
        "skill.check_materials",
        "skill.calculate_capacity",
        "skills_parallel",
        "executant_candidates",
        "optimization",
        "verification",
        "proposal_ready",
    ]
    por_stage = {event.stage: event for event in first.trace_events}
    janela = por_stage["skills_parallel"].elapsed_ms
    for nome in (
        "skill.rank_backlog",
        "skill.estimate_duration",
        "skill.check_materials",
        "skill.calculate_capacity",
    ):
        assert por_stage[nome].counts
        assert por_stage[nome].elapsed_ms <= janela


def test_cli_writes_auditable_outputs(tmp_path: Path) -> None:
    snapshot_file = tmp_path / "snapshot.json"
    output_dir = tmp_path / "output"
    snapshot_file.write_text(_snapshot().model_dump_json(indent=2), encoding="utf-8")

    exit_code = main(
        [
            "generate-proposal",
            "--snapshot-file",
            str(snapshot_file),
            "--period-start",
            PERIOD.start.isoformat(),
            "--period-end",
            PERIOD.end.isoformat(),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert {path.name for path in output_dir.iterdir()} == {
        "proposal.json",
        "verification.json",
        "summary.json",
        "trace.jsonl",
        "enrichment.json",
        "request.json",
        "config.json",
    }
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["assignments"] == 2
    assert summary["violations"] == 0
    proposal_payload = json.loads(
        (output_dir / "proposal.json").read_text(encoding="utf-8")
    )
    assert len(proposal_payload["skill_versions"]) == 5
    config_payload = json.loads((output_dir / "config.json").read_text(encoding="utf-8"))
    request_payload = json.loads((output_dir / "request.json").read_text(encoding="utf-8"))
    assert request_payload["weights_version"] == derive_weights_version(
        PlanningConfig.model_validate(config_payload)
    )
    assert proposal_payload["weights_version"] == request_payload["weights_version"]

    enrichment = json.loads(
        (output_dir / "enrichment.json").read_text(encoding="utf-8")
    )
    assert len(enrichment["operations"]) == 2
    assert len(enrichment["capacities"]) == 2
    assert enrichment["operations"][0]["executants"]

    trace = [
        json.loads(line)
        for line in (output_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["stage"] for event in trace[:-1]] == [
        "snapshot_validated",
        "skill.rank_backlog",
        "skill.estimate_duration",
        "skill.check_materials",
        "skill.calculate_capacity",
        "skills_parallel",
        "executant_candidates",
        "optimization",
        "verification",
        "proposal_ready",
    ]
    assert trace[-1]["event"] == "planning_run_completed"
