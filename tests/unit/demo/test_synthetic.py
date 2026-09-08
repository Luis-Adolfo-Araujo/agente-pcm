"""O mundo fictício precisa ser reprodutível e passar pelo contrato canônico."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from application.demo.synthetic import (
    PLANT_TIMEZONE,
    build_demo_snapshot,
    demo_period,
)
from application.pilot.store import WEEKLY_HOURS_LIMIT, SnapshotCatalog
from application.workflows.generate_schedule import generate_schedule
from domain.planning.config import PlanningConfig
from domain.planning.entities import PlanningRequest, PlanningSnapshot
from domain.planning.enums import UnscheduledReason


def _small(**overrides: object) -> PlanningSnapshot:
    """Um mundo menor: os testes não precisam do backlog inteiro para provar a forma."""

    arguments: dict[str, Any] = {"operation_count": 240, "inventory_items": 400}
    arguments.update(overrides)
    return build_demo_snapshot(**arguments)


def _dump(snapshot: PlanningSnapshot) -> str:
    return json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)


def test_same_seed_rebuilds_the_same_snapshot() -> None:
    assert _dump(_small()) == _dump(_small())


def test_another_seed_builds_another_world() -> None:
    first = _small(seed=1)
    second = _small(seed=2)

    assert _dump(first) != _dump(second)
    assert first.snapshot_id != second.snapshot_id


def test_rejects_an_empty_world() -> None:
    with pytest.raises(ValueError):
        build_demo_snapshot(operation_count=0)
    with pytest.raises(ValueError):
        build_demo_snapshot(inventory_items=0)


def test_rejects_a_naive_as_of() -> None:
    with pytest.raises(ValueError):
        _small(as_of=datetime(2026, 8, 17, 12))


def test_the_catalog_accepts_the_generated_file(tmp_path: Path) -> None:
    snapshot = _small()
    path = tmp_path / "demo.json"
    path.write_text(
        json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False),
        encoding="utf-8",
    )

    summaries = SnapshotCatalog(tmp_path).list()

    assert [item.snapshot_id for item in summaries] == [snapshot.snapshot_id]
    assert summaries[0].source == "sintetico"


def test_the_week_starts_on_a_monday_after_the_cut() -> None:
    snapshot = _small()
    period = demo_period(snapshot)

    assert period.start.tzinfo is not None
    assert period.start.astimezone(PLANT_TIMEZONE).weekday() == 0
    assert period.start > snapshot.as_of
    assert period.end - period.start == timedelta(days=7)


def test_availability_stays_inside_the_planned_week() -> None:
    snapshot = _small()
    period = demo_period(snapshot)

    assert snapshot.availability
    for slot in snapshot.availability:
        assert period.start <= slot.window.start
        assert slot.window.end <= period.end


def test_one_worker_declares_a_week_above_the_legal_limit() -> None:
    """O indicador de qualidade só prova algo se houver um caso para pegar."""

    snapshot = _small()
    minutes: dict[str, float] = {}
    for slot in snapshot.availability:
        minutes[slot.worker_id] = minutes.get(slot.worker_id, 0.0) + slot.window.minutes

    above = [worker_id for worker_id, total in minutes.items() if total / 60 > WEEKLY_HOURS_LIMIT]

    assert len(above) == 1


def test_the_history_feeds_the_duration_estimate() -> None:
    snapshot = _small()
    titles = {item.title for item in snapshot.history}

    assert titles
    assert {operation.title for operation in snapshot.operations} <= titles


def test_a_full_run_is_valid_and_shows_every_barrier() -> None:
    snapshot = build_demo_snapshot()
    period = demo_period(snapshot)
    request = PlanningRequest(
        tenant_id=snapshot.tenant_id, period=period, as_of=snapshot.as_of
    )

    result = asyncio.run(generate_schedule(request, snapshot, PlanningConfig()))
    solution = result.proposal.solution
    reasons = {item.reason for item in solution.unscheduled}

    assert result.proposal.verification.valid
    assert not result.proposal.verification.violations
    assert solution.assignments
    assert all(assignment.worker_ids for assignment in solution.assignments)
    assert {
        UnscheduledReason.NO_CAPACITY,
        UnscheduledReason.MATERIAL,
        UnscheduledReason.BLOCKED,
    } <= reasons


def test_the_run_is_reproducible_over_the_demo_world() -> None:
    snapshot = _small()
    period = demo_period(snapshot)
    request = PlanningRequest(
        tenant_id=snapshot.tenant_id, period=period, as_of=snapshot.as_of
    )

    first = asyncio.run(generate_schedule(request, snapshot, PlanningConfig()))
    second = asyncio.run(generate_schedule(request, snapshot, PlanningConfig()))

    assert first.proposal.proposal_id == second.proposal.proposal_id
    assert first.proposal.solution == second.proposal.solution
