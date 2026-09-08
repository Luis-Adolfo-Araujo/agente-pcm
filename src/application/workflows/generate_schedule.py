"""Workflow coordenador do Agente Programador."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from collections.abc import Callable
from typing import Any, TypeVar

from agent.trace.writer import PlanningTraceRecorder
from application.skills.calculate_capacity import run_calculate_capacity
from application.skills.check_materials import run_check_materials
from application.skills.estimate_duration import run_estimate_duration
from application.skills.rank_backlog import run_rank_backlog
from application.skills.suggest_executants import run_suggest_executants
from domain.planning.adjustments import PlanningConstraints, apply_constraints
from domain.planning.config import PlanningConfig
from domain.planning.entities import (
    EnrichedOperation,
    PlanningRequest,
    PlanningRunResult,
    PlanningSnapshot,
    PlanningStageTrace,
    ScheduleProposal,
)
from domain.planning.enums import ProposalStatus
from domain.planning.optimizer import optimize_schedule
from domain.planning.verifier import verify_schedule

T = TypeVar("T")


def _timed(skill: Callable[..., T], *args: Any) -> tuple[T, float]:
    """Rodar uma skill medindo o próprio tempo dela.

    As quatro skills do TaskGroup rodam ao mesmo tempo: o relógio de fora só sabe
    dizer quanto durou a janela inteira. Quem quer auditar precisa do tempo de cada
    uma, então cada skill é cronometrada dentro da própria thread.
    """

    started_ns = time.perf_counter_ns()
    result = skill(*args)
    return result, (time.perf_counter_ns() - started_ns) / 1_000_000


def _proposal_id(
    request: PlanningRequest,
    snapshot: PlanningSnapshot,
    solution_hash: str,
    skill_versions: dict[str, str],
) -> str:
    identity = "|".join(
        (
            request.tenant_id,
            snapshot.snapshot_id,
            request.period.start.isoformat(),
            request.period.end.isoformat(),
            request.as_of.isoformat(),
            request.ruleset_version,
            request.weights_version,
            solution_hash,
            json.dumps(skill_versions, sort_keys=True, separators=(",", ":")),
        )
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))


async def generate_schedule(
    request: PlanningRequest,
    snapshot: PlanningSnapshot,
    config: PlanningConfig | None = None,
    skill_versions: dict[str, str] | None = None,
    stage_listener: Callable[[PlanningStageTrace], None] | None = None,
    constraints: PlanningConstraints | None = None,
) -> PlanningRunResult:
    """Executar as skills, otimizar e verificar uma proposta em dry-run."""

    trace = PlanningTraceRecorder(listener=stage_listener)
    stage_started = trace.start()
    config = config or PlanningConfig()
    skill_versions = dict(sorted((skill_versions or {}).items()))
    if request.tenant_id != snapshot.tenant_id:
        raise ValueError("request and snapshot tenant_id do not match")
    if request.as_of != snapshot.as_of:
        raise ValueError("request as_of must match the immutable snapshot as_of")
    if not request.dry_run:
        raise ValueError("the offline workflow only supports dry_run=true")
    trace.complete(
        "snapshot_validated",
        stage_started,
        counts={
            "history": len(snapshot.history),
            "inventory": len(snapshot.inventory),
            "operations": len(snapshot.operations),
            "workers": len(snapshot.workers),
        },
    )

    stage_started = trace.start()
    async with asyncio.TaskGroup() as group:
        ranking_task = group.create_task(
            asyncio.to_thread(
                _timed,
                run_rank_backlog,
                snapshot.operations,
                request.as_of,
                config.ranking,
            )
        )
        duration_task = group.create_task(
            asyncio.to_thread(
                _timed,
                run_estimate_duration,
                snapshot.operations,
                snapshot.history,
                request.as_of,
                config.duration,
            )
        )
        materials_task = group.create_task(
            asyncio.to_thread(
                _timed,
                run_check_materials,
                snapshot.operations,
                snapshot.inventory,
                request.period.end,
                config.materials,
            )
        )
        capacity_task = group.create_task(
            asyncio.to_thread(
                _timed,
                run_calculate_capacity,
                snapshot.workers,
                snapshot.availability,
                snapshot.existing_assignments,
                request.period,
            )
        )

    priorities, ranking_ms = ranking_task.result()
    durations, duration_ms = duration_task.result()
    materials, materials_ms = materials_task.result()
    capacities, capacity_ms = capacity_task.result()
    trace.record("skill.rank_backlog", ranking_ms, counts={"priorities": len(priorities)})
    trace.record("skill.estimate_duration", duration_ms, counts={"durations": len(durations)})
    trace.record("skill.check_materials", materials_ms, counts={"materials": len(materials)})
    trace.record("skill.calculate_capacity", capacity_ms, counts={"capacities": len(capacities)})
    trace.complete(
        "skills_parallel",
        stage_started,
        counts={
            "capacities": len(capacities),
            "durations": len(durations),
            "materials": len(materials),
            "priorities": len(priorities),
        },
    )

    stage_started = trace.start()
    executants = run_suggest_executants(
        snapshot.operations,
        durations,
        capacities,
        snapshot.workers,
        snapshot.history,
        request.as_of,
        config.executants,
    )

    priorities_by_id = {item.operation_id: item for item in priorities}
    durations_by_id = {item.operation_id: item for item in durations}
    materials_by_id = {item.operation_id: item for item in materials}
    enriched = tuple(
        EnrichedOperation(
            operation=operation,
            priority=priorities_by_id[operation.operation_id],
            duration=durations_by_id[operation.operation_id],
            materials=materials_by_id[operation.operation_id],
            executants=executants.get(operation.operation_id, ()),
        )
        for operation in snapshot.operations
    )
    trace.complete(
        "executant_candidates",
        stage_started,
        counts={
            "candidates": sum(len(items) for items in executants.values()),
            "operations": len(enriched),
        },
    )

    stage_started = trace.start()
    # A restrição filtra só o que entra no otimizador: o `enriched` completo
    # segue intacto para `PlanningRunResult` e para `verify_schedule` logo
    # abaixo — ela tira a ordem da otimização, não do backlog.
    enriched_to_optimize, capacities_to_optimize = (
        apply_constraints(enriched, capacities, constraints, request)
        if constraints is not None
        else (enriched, capacities)
    )
    solution = optimize_schedule(
        enriched_to_optimize, capacities_to_optimize, request, config.optimizer
    )
    trace.complete(
        "optimization",
        stage_started,
        counts={
            "assignments": len(solution.assignments),
            "unscheduled": len(solution.unscheduled),
        },
    )
    stage_started = trace.start()
    verification = verify_schedule(solution, snapshot, enriched, request)
    trace.complete(
        "verification",
        stage_started,
        counts={"violations": len(verification.violations)},
    )
    stage_started = trace.start()
    solution_hash = hashlib.sha256(
        solution.model_dump_json(exclude_none=True).encode("utf-8")
    ).hexdigest()
    proposal = ScheduleProposal(
        proposal_id=_proposal_id(request, snapshot, solution_hash, skill_versions),
        tenant_id=request.tenant_id,
        snapshot_id=snapshot.snapshot_id,
        created_at=request.as_of,
        period=request.period,
        status=ProposalStatus.DRAFT if verification.valid else ProposalStatus.INVALID,
        solution=solution,
        verification=verification,
        ruleset_version=request.ruleset_version,
        weights_version=request.weights_version,
        skill_versions=skill_versions,
    )
    trace.complete(
        "proposal_ready",
        stage_started,
        counts={"proposals": 1},
    )
    return PlanningRunResult(
        proposal=proposal,
        priorities=priorities,
        durations=durations,
        materials=materials,
        capacities=capacities,
        enriched=enriched,
        trace_events=trace.events,
    )
