"""Fixtures mínimas e consistentes para os testes do domínio de planejamento.

A forma dos objetos segue `tests/end_to_end/test_generate_schedule.py`: mesmos
campos, mesma ideia de operação/trabalhador/janela. Os seis construtores
descrevem o mesmo mundo — dois trabalhadores, três operações, duas escalas —
para que uma solução (`solution_base`) e a capacidade calculada dela
(`capacities_base`) façam sentido junto do snapshot e do enriquecimento
(`snapshot_base`, `enriched_base`) que as originaram. `run_base` amarra
`snapshot_base` e `request_base` numa run em fila, para os testes de
persistência do piloto.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from application.pilot.models import PilotRun, RunStatus
from domain.planning.config import PlanningConfig
from domain.planning.entities import (
    AvailabilitySlot,
    CapacityAssessment,
    CapacitySlot,
    DurationEstimate,
    EnrichedOperation,
    ExecutorCandidate,
    MaterialAssessment,
    PlanningRequest,
    PlanningSnapshot,
    PriorityAssessment,
    ScheduleAssignment,
    SchedulingSolution,
    TimeWindow,
    UnscheduledOperation,
    WorkerProfile,
    WorkOrderOperation,
)
from domain.planning.enums import (
    DurationSource,
    MaterialStatus,
    SolutionStatus,
    UnscheduledReason,
)

AS_OF = datetime(2026, 8, 17, 12, tzinfo=UTC)
SHIFT_DAYS = (date(2026, 8, 19), date(2026, 8, 20))
OPERATION_IDS = ("op-high", "op-medium", "op-out")


def _shift_window(day: date) -> TimeWindow:
    return TimeWindow(
        start=datetime(day.year, day.month, day.day, 8, tzinfo=UTC),
        end=datetime(day.year, day.month, day.day, 16, tzinfo=UTC),
    )


def _operation(operation_id: str) -> WorkOrderOperation:
    return WorkOrderOperation(
        work_order_id=f"wo-{operation_id}",
        operation_id=operation_id,
        title=f"Operação {operation_id}",
        status="open",
        planning_status="unplanned",
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        due_at=datetime(2026, 8, 24, tzinfo=UTC),
        priority_level=1,
        asset_id="asset-1",
        planned_team_id="mechanical",
        planned_duration_minutes=60,
    )


def snapshot_base() -> PlanningSnapshot:
    """Dois trabalhadores ativos, escala das 8h-16h nos dias 19 e 20/08/2026."""

    return PlanningSnapshot(
        snapshot_id="fixture-adjustments",
        tenant_id="planta-modelo",
        as_of=AS_OF,
        operations=tuple(_operation(operation_id) for operation_id in OPERATION_IDS),
        workers=(
            WorkerProfile(worker_id="w-1", team_ids=("mechanical",)),
            WorkerProfile(worker_id="w-2", team_ids=("mechanical",)),
        ),
        availability=tuple(
            AvailabilitySlot(worker_id=worker_id, window=_shift_window(day))
            for worker_id in ("w-1", "w-2")
            for day in SHIFT_DAYS
        ),
    )


def enriched_base() -> tuple[EnrichedOperation, ...]:
    """Mesmas três operações do snapshot, cada uma com 60 minutos de duração."""

    return tuple(
        EnrichedOperation(
            operation=operation,
            priority=PriorityAssessment(
                operation_id=operation.operation_id,
                score=80.0,
                band="high",
                model="fixture",
                components=(),
                reason_codes=(),
            ),
            duration=DurationEstimate(
                operation_id=operation.operation_id,
                minutes=60,
                p50_minutes=60,
                p80_minutes=60,
                source=DurationSource.PLANNED,
                sample_size=1,
                confidence=1.0,
                reason_codes=(),
            ),
            materials=MaterialAssessment(
                operation_id=operation.operation_id,
                status=MaterialStatus.NOT_REQUIRED,
                blocking=False,
                reason_codes=(),
            ),
            executants=(
                ExecutorCandidate(
                    operation_id=operation.operation_id,
                    worker_id="w-1",
                    score=80.0,
                    eligible=True,
                    available_minutes=480,
                    reason_codes=(),
                ),
            ),
        )
        for operation in snapshot_base().operations
    )


def capacities_base() -> tuple[CapacityAssessment, ...]:
    """Capacidade que `calculate_capacity` produziria a partir de `snapshot_base`.

    Sem compromissos existentes, cada trabalhador tem os dois turnos inteiros
    livres: 2 dias x 8h = 960 minutos brutos e líquidos, um `CapacitySlot` por
    dia.
    """

    return tuple(
        CapacityAssessment(
            worker_id=worker_id,
            gross_minutes=960,
            committed_minutes=0,
            net_minutes=960,
            slots=tuple(
                CapacitySlot(worker_id=worker_id, window=_shift_window(day))
                for day in SHIFT_DAYS
            ),
        )
        for worker_id in ("w-1", "w-2")
    )


def request_base() -> PlanningRequest:
    """Período de 18 a 25/08/2026, em modo dry-run."""

    return PlanningRequest(
        tenant_id="planta-modelo",
        period=TimeWindow(
            start=datetime(2026, 8, 18, tzinfo=UTC),
            end=datetime(2026, 8, 25, tzinfo=UTC),
        ),
        as_of=AS_OF,
        dry_run=True,
    )


def run_base() -> PilotRun:
    """Run em fila, no mesmo mundo de `snapshot_base` e `request_base`.

    Espelha o que `PilotService.start_run` monta: mesmo `tenant_id` e
    `snapshot_id` do snapshot da fixture, status `QUEUED` (única compatível
    com uma run recém-criada) e configuração padrão.
    """

    return PilotRun(
        run_id="run-fixture",
        snapshot_id=snapshot_base().snapshot_id,
        tenant_id="planta-modelo",
        status=RunStatus.QUEUED,
        created_at=AS_OF,
        request=request_base(),
        config=PlanningConfig(),
    )


def solution_base() -> SchedulingSolution:
    """`op-high` e `op-medium` alocadas para `w-1` no dia 19; `op-out` de fora."""

    day = SHIFT_DAYS[0]
    first_slot = TimeWindow(
        start=datetime(day.year, day.month, day.day, 8, tzinfo=UTC),
        end=datetime(day.year, day.month, day.day, 9, tzinfo=UTC),
    )
    second_slot = TimeWindow(
        start=datetime(day.year, day.month, day.day, 9, tzinfo=UTC),
        end=datetime(day.year, day.month, day.day, 10, tzinfo=UTC),
    )
    return SchedulingSolution(
        status=SolutionStatus.PARTIAL,
        assignments=(
            ScheduleAssignment(
                work_order_id="wo-op-high",
                operation_id="op-high",
                worker_ids=("w-1",),
                window=first_slot,
                priority_score=80.0,
                reason_codes=(),
            ),
            ScheduleAssignment(
                work_order_id="wo-op-medium",
                operation_id="op-medium",
                worker_ids=("w-1",),
                window=second_slot,
                priority_score=70.0,
                reason_codes=(),
            ),
        ),
        unscheduled=(
            UnscheduledOperation(
                work_order_id="wo-op-out",
                operation_id="op-out",
                reason=UnscheduledReason.NO_CAPACITY,
                details=(),
            ),
        ),
        objective_value=150.0,
        algorithm_version="greedy-v1",
    )
