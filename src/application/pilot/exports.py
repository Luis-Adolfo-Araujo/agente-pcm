"""Exportações estáveis do piloto, sem dependência de UI."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from typing import Any

from application.pilot.models import ExportBundle, ExportFormat, PilotRun, RunSummary
from domain.planning.entities import PlanningRunResult, PlanningStageTrace


def run_summary(result: PlanningRunResult) -> RunSummary:
    proposal = result.proposal
    return RunSummary(
        proposal_status=proposal.status.value,
        verification_valid=proposal.verification.valid,
        assignments=len(proposal.solution.assignments),
        unscheduled=len(proposal.solution.unscheduled),
        violations=len(proposal.verification.violations),
        objective_value=proposal.solution.objective_value,
        # Eventos "skill.*" são medições aninhadas dentro de skills_parallel: somá-los
        # aqui contaria o mesmo tempo de parede duas vezes.
        trace_elapsed_ms=round(
            sum(
                event.elapsed_ms
                for event in result.trace_events
                if not event.stage.startswith("skill.")
            ),
            3,
        ),
    )


def _json_text(payload: Any) -> str:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
            default=str,
        )
        + "\n"
    )


def _trace_jsonl(events: Iterable[PlanningStageTrace], summary: RunSummary) -> str:
    lines = [
        json.dumps(
            {
                "event": "planning_stage_completed",
                **event.model_dump(mode="json"),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for event in events
    ]
    lines.append(
        json.dumps(
            {
                "event": "planning_run_completed",
                **summary.model_dump(mode="json"),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return "\n".join(lines) + "\n"


def json_export(run: PilotRun, result: PlanningRunResult) -> ExportBundle:
    summary = run.summary or run_summary(result)
    files = {
        "run.json": _json_text(run.model_dump(mode="json")),
        "request.json": _json_text(run.request.model_dump(mode="json")),
        "config.json": _json_text(run.config.model_dump(mode="json")),
        "result.json": _json_text(result.model_dump(mode="json")),
        "proposal.json": _json_text(result.proposal.model_dump(mode="json")),
        "verification.json": _json_text(result.proposal.verification.model_dump(mode="json")),
        "enrichment.json": _json_text(
            {
                "schema_version": "1.0",
                "operations": [item.model_dump(mode="json") for item in result.enriched],
                "capacities": [item.model_dump(mode="json") for item in result.capacities],
            }
        ),
        "summary.json": _json_text(summary.model_dump(mode="json")),
        "trace.jsonl": _trace_jsonl(result.trace_events, summary),
    }
    media_types = {
        name: ("application/x-ndjson" if name.endswith(".jsonl") else "application/json")
        for name in files
    }
    return ExportBundle(
        run_id=run.run_id,
        format=ExportFormat.JSON,
        files=files,
        media_types=media_types,
    )


def _safe_csv_value(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _csv_text(fieldnames: tuple[str, ...], rows: Iterable[Mapping[str, Any]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(fieldnames),
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _safe_csv_value(value) for key, value in row.items()})
    return buffer.getvalue()


def _ranking_csv(result: PlanningRunResult) -> str:
    enriched_by_id = {item.operation.operation_id: item for item in result.enriched}
    scheduled_ids = {assignment.operation_id for assignment in result.proposal.solution.assignments}
    rows: list[dict[str, Any]] = []
    for position, priority in enumerate(result.priorities, start=1):
        enriched = enriched_by_id[priority.operation_id]
        operation = enriched.operation
        components = {component.name: component for component in priority.components}

        def raw(name: str, source: Mapping[str, Any] = components) -> float | None:
            component = source.get(name)
            return None if component is None else component.raw_value

        def normalized(name: str, source: Mapping[str, Any] = components) -> float | None:
            component = source.get(name)
            return None if component is None else component.normalized_value

        def contribution(name: str, source: Mapping[str, Any] = components) -> float | None:
            component = source.get(name)
            return None if component is None else component.contribution

        rows.append(
            {
                "position": position,
                "work_order_id": operation.work_order_id,
                "operation_id": operation.operation_id,
                "title": operation.title,
                "status": operation.status,
                "planning_status": operation.planning_status,
                "priority_level": operation.priority_level,
                "created_at": operation.created_at.isoformat(),
                "due_at": operation.due_at.isoformat() if operation.due_at else None,
                "criticality": operation.criticality,
                "score": priority.score,
                "band": priority.band,
                "model": priority.model,
                "priority_raw": raw("priority"),
                "priority_normalized": normalized("priority"),
                "priority_contribution": contribution("priority"),
                "age_days": raw("age"),
                "age_normalized": normalized("age"),
                "age_contribution": contribution("age"),
                "sla_days_remaining": raw("sla"),
                "sla_normalized": normalized("sla"),
                "sla_contribution": contribution("sla"),
                "criticality_contribution": contribution("criticality"),
                "reason_codes": "|".join(priority.reason_codes),
                "missing_fields": "|".join(priority.missing_fields),
                "duration_minutes": enriched.duration.minutes,
                "duration_source": enriched.duration.source.value,
                "duration_confidence": enriched.duration.confidence,
                "material_status": enriched.materials.status.value,
                "material_blocking": enriched.materials.blocking,
                "scheduled": operation.operation_id in scheduled_ids,
            }
        )
    return _csv_text(
        (
            "position",
            "work_order_id",
            "operation_id",
            "title",
            "status",
            "planning_status",
            "priority_level",
            "created_at",
            "due_at",
            "criticality",
            "score",
            "band",
            "model",
            "priority_raw",
            "priority_normalized",
            "priority_contribution",
            "age_days",
            "age_normalized",
            "age_contribution",
            "sla_days_remaining",
            "sla_normalized",
            "sla_contribution",
            "criticality_contribution",
            "reason_codes",
            "missing_fields",
            "duration_minutes",
            "duration_source",
            "duration_confidence",
            "material_status",
            "material_blocking",
            "scheduled",
        ),
        rows,
    )


def _schedule_csv(result: PlanningRunResult) -> str:
    return _csv_text(
        (
            "work_order_id",
            "operation_id",
            "worker_ids",
            "start",
            "end",
            "duration_minutes",
            "priority_score",
            "reason_codes",
        ),
        (
            {
                "work_order_id": assignment.work_order_id,
                "operation_id": assignment.operation_id,
                "worker_ids": "|".join(assignment.worker_ids),
                "start": assignment.window.start.isoformat(),
                "end": assignment.window.end.isoformat(),
                "duration_minutes": assignment.window.minutes,
                "priority_score": assignment.priority_score,
                "reason_codes": "|".join(assignment.reason_codes),
            }
            for assignment in result.proposal.solution.assignments
        ),
    )


def _unscheduled_csv(result: PlanningRunResult) -> str:
    enriched_by_id = {item.operation.operation_id: item for item in result.enriched}
    return _csv_text(
        (
            "work_order_id",
            "operation_id",
            "title",
            "priority_score",
            "reason",
            "details",
        ),
        (
            {
                "work_order_id": item.work_order_id,
                "operation_id": item.operation_id,
                "title": enriched_by_id[item.operation_id].operation.title,
                "priority_score": enriched_by_id[item.operation_id].priority.score,
                "reason": item.reason.value,
                "details": "|".join(item.details),
            }
            for item in result.proposal.solution.unscheduled
        ),
    )


def csv_export(run: PilotRun, result: PlanningRunResult) -> ExportBundle:
    files = {
        "ranking.csv": _ranking_csv(result),
        "schedule.csv": _schedule_csv(result),
        "unscheduled.csv": _unscheduled_csv(result),
    }
    return ExportBundle(
        run_id=run.run_id,
        format=ExportFormat.CSV,
        files=files,
        media_types={name: "text/csv; charset=utf-8" for name in files},
    )


def export_bundle(
    run: PilotRun,
    result: PlanningRunResult,
    format: ExportFormat,
) -> ExportBundle:
    if format is ExportFormat.JSON:
        return json_export(run, result)
    return csv_export(run, result)
