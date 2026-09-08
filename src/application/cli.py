"""CLI offline do primeiro incremento do Agente Programador."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.programmer.coordinator import ProgrammerAgent
from agent.trace.writer import write_trace_jsonl
from application.config import derive_weights_version, load_planning_config
from application.demo.synthetic import (
    DEFAULT_INVENTORY_ITEMS,
    DEFAULT_OPERATION_COUNT,
    DEFAULT_SEED,
    DEFAULT_TENANT_ID,
    build_demo_snapshot,
)
from application.notes.triage import treat_notes
from application.pilot.golden_set import golden_set_jsonl
from application.pilot.store import SQLitePilotStore
from application.workflows.decide_proposal import decide_proposal
from domain.notes.config import NoteTriageConfig
from domain.planning.config import PlanningConfig
from domain.planning.entities import (
    HumanDecision,
    PlanningRequest,
    PlanningRunResult,
    PlanningSnapshot,
    ScheduleProposal,
    TimeWindow,
)
from domain.planning.enums import DecisionType
from infrastructure.database.tractian.repository import (
    TractianNoteRepository,
    TractianPlanningRepository,
)


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("datetime must include timezone")
    return parsed


def _atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_outputs(
    output_dir: Path,
    result: PlanningRunResult,
    *,
    request: PlanningRequest | None = None,
    config: PlanningConfig | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    proposal = result.proposal
    _atomic_json(output_dir / "proposal.json", proposal.model_dump(mode="json"))
    _atomic_json(
        output_dir / "verification.json",
        proposal.verification.model_dump(mode="json"),
    )
    _atomic_json(
        output_dir / "enrichment.json",
        {
            "schema_version": "1.0",
            "operations": [item.model_dump(mode="json") for item in result.enriched],
            "capacities": [item.model_dump(mode="json") for item in result.capacities],
        },
    )
    if request is not None:
        _atomic_json(output_dir / "request.json", request.model_dump(mode="json"))
    if config is not None:
        _atomic_json(output_dir / "config.json", config.model_dump(mode="json"))
    summary = {
        "proposal_id": proposal.proposal_id,
        "status": proposal.status.value,
        "assignments": len(proposal.solution.assignments),
        "unscheduled": len(proposal.solution.unscheduled),
        "violations": len(proposal.verification.violations),
        "objective_value": proposal.solution.objective_value,
    }
    _atomic_json(output_dir / "summary.json", summary)
    trace = {
        "event": "planning_run_completed",
        "proposal_id": proposal.proposal_id,
        "tenant_id": proposal.tenant_id,
        "snapshot_id": proposal.snapshot_id,
        **summary,
    }
    write_trace_jsonl(
        output_dir / "trace.jsonl",
        result.trace_events,
        completion_event=trace,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="maia-pcm")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate-proposal")
    generate.add_argument("--snapshot-file", required=True, type=Path)
    generate.add_argument("--period-start", required=True, type=_parse_datetime)
    generate.add_argument("--period-end", required=True, type=_parse_datetime)
    generate.add_argument("--as-of", type=_parse_datetime)
    generate.add_argument("--tenant")
    generate.add_argument("--config", type=Path)
    generate.add_argument("--output-dir", required=True, type=Path)

    extract = commands.add_parser("extract-snapshot")
    extract.add_argument("--tenant", required=True)
    extract.add_argument("--period-start", required=True, type=_parse_datetime)
    extract.add_argument("--period-end", required=True, type=_parse_datetime)
    extract.add_argument("--as-of", required=True, type=_parse_datetime)
    extract.add_argument("--dsn-env", default="SOURCE_DATABASE_DSN")
    extract.add_argument("--output", required=True, type=Path)

    decide = commands.add_parser("decide-proposal")
    decide.add_argument("--proposal-file", required=True, type=Path)
    decide.add_argument("--decision", required=True, choices=[item.value for item in DecisionType])
    decide.add_argument("--decided-by", required=True)
    decide.add_argument("--decided-at", required=True, type=_parse_datetime)
    decide.add_argument("--reason", required=True)
    decide.add_argument("--output", required=True, type=Path)

    notes = commands.add_parser("triage-notes")
    notes.add_argument("--tenant", required=True)
    notes.add_argument("--as-of", required=True, type=_parse_datetime)
    notes.add_argument("--dsn-env", default="SOURCE_DATABASE_DSN")
    notes.add_argument("--output", required=True, type=Path)

    demo = commands.add_parser("generate-demo-snapshot")
    demo.add_argument("--output", required=True, type=Path)
    demo.add_argument("--seed", type=int, default=DEFAULT_SEED)
    demo.add_argument("--as-of", type=_parse_datetime)
    demo.add_argument("--operations", type=int, default=DEFAULT_OPERATION_COUNT)
    demo.add_argument("--inventory-items", type=int, default=DEFAULT_INVENTORY_ITEMS)
    demo.add_argument("--tenant", default=DEFAULT_TENANT_ID)

    golden = commands.add_parser("export-golden-set")
    golden.add_argument("--db", required=True, type=Path)
    golden.add_argument("--output", required=True, type=Path)
    golden.add_argument("--run")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "triage-notes":
        dsn = os.environ.get(args.dsn_env)
        if not dsn:
            raise SystemExit(f"database DSN is missing from environment variable {args.dsn_env}")
        batch = TractianNoteRepository(dsn).load_batch(
            tenant_id=args.tenant,
            as_of=args.as_of,
        )
        triage = treat_notes(batch, NoteTriageConfig())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        _atomic_json(args.output, triage.model_dump(mode="json"))
        return 0

    if args.command == "generate-demo-snapshot":
        snapshot = build_demo_snapshot(
            seed=args.seed,
            as_of=args.as_of,
            operation_count=args.operations,
            inventory_items=args.inventory_items,
            tenant_id=args.tenant,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        _atomic_json(args.output, snapshot.model_dump(mode="json"))
        return 0

    if args.command == "export-golden-set":
        store = SQLitePilotStore(args.db)
        store.initialize()
        records = store.list_feedback(args.run)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(golden_set_jsonl(records), encoding="utf-8")
        return 0

    if args.command == "extract-snapshot":
        dsn = os.environ.get(args.dsn_env)
        if not dsn:
            raise SystemExit(f"database DSN is missing from environment variable {args.dsn_env}")
        period = TimeWindow(start=args.period_start, end=args.period_end)
        snapshot = TractianPlanningRepository(dsn).load_snapshot(
            tenant_id=args.tenant,
            as_of=args.as_of,
            period=period,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        _atomic_json(args.output, snapshot.model_dump(mode="json"))
        return 0

    if args.command == "decide-proposal":
        proposal = ScheduleProposal.model_validate_json(
            args.proposal_file.read_text(encoding="utf-8")
        )
        reviewed = decide_proposal(
            proposal,
            HumanDecision(
                proposal_id=proposal.proposal_id,
                decision=DecisionType(args.decision),
                decided_by=args.decided_by,
                decided_at=args.decided_at,
                reason=args.reason,
            ),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        _atomic_json(args.output, reviewed.model_dump(mode="json"))
        return 0

    snapshot = PlanningSnapshot.model_validate_json(
        args.snapshot_file.read_text(encoding="utf-8")
    )
    config = load_planning_config(args.config)
    request = PlanningRequest(
        tenant_id=args.tenant or snapshot.tenant_id,
        period=TimeWindow(start=args.period_start, end=args.period_end),
        as_of=args.as_of or snapshot.as_of,
        weights_version=derive_weights_version(config),
        dry_run=True,
    )
    result = asyncio.run(ProgrammerAgent(config).propose(request, snapshot))
    _write_outputs(args.output_dir, result, request=request, config=config)
    return 0 if result.proposal.verification.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
