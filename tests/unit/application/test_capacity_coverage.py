from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from application.pilot.coverage import capacity_coverage
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
    end=datetime(2026, 8, 18, 12, tzinfo=UTC),
)


def _operation(identifier: str, minutes: int) -> WorkOrderOperation:
    return WorkOrderOperation(
        work_order_id=f"wo-{identifier}",
        operation_id=identifier,
        title=f"Tarefa {identifier}",
        status="open",
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        due_at=datetime(2026, 8, 20, tzinfo=UTC),
        priority_level=1,
        asset_id="asset-1",
        planned_team_id="mechanical",
        planned_duration_minutes=minutes,
    )


def _result(operation_count: int, worker_count: int) -> PlanningRunResult:
    """Cria uma demanda de 120 min por operação contra a capacidade informada."""

    snapshot = PlanningSnapshot(
        snapshot_id="coverage-fixture",
        tenant_id="planta-modelo",
        as_of=AS_OF,
        operations=tuple(
            _operation(f"op-{index}", 120) for index in range(operation_count)
        ),
        workers=tuple(
            WorkerProfile(worker_id=f"worker-{index}", team_ids=("mechanical",))
            for index in range(worker_count)
        ),
        availability=tuple(
            AvailabilitySlot(worker_id=f"worker-{index}", window=PERIOD)
            for index in range(worker_count)
        ),
    )
    request = PlanningRequest(tenant_id="planta-modelo", period=PERIOD, as_of=AS_OF)
    return asyncio.run(generate_schedule(request, snapshot, PlanningConfig()))


def test_coverage_is_complete_when_capacity_absorbs_the_whole_backlog() -> None:
    coverage = capacity_coverage(_result(operation_count=2, worker_count=2))

    assert coverage.demand_minutes == 240
    assert coverage.available_minutes == 480
    assert coverage.coverage_percent == 100.0
    assert coverage.scheduled_operations == 2
    assert coverage.capacity_limited_operations == 0


def test_coverage_separates_the_physical_limit_from_recommendation_failure() -> None:
    coverage = capacity_coverage(_result(operation_count=6, worker_count=1))

    assert coverage.demand_minutes == 720
    assert coverage.available_minutes == 240
    assert coverage.coverage_percent == 33.33
    assert coverage.scheduled_operations == 2
    assert coverage.unscheduled_operations == 4
    assert coverage.capacity_limited_operations == 4
    assert coverage.reasons["no_capacity"] == 4


def test_coverage_reports_zero_capacity_without_dividing_by_zero() -> None:
    coverage = capacity_coverage(_result(operation_count=1, worker_count=0))

    assert coverage.available_minutes == 0
    assert coverage.coverage_percent == 0.0
    assert coverage.scheduled_operations == 0
