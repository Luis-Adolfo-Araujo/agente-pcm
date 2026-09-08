"""Ajustes que o PCM aplica sobre uma proposta já montada.

A proposta do agente é imutável: o que a pessoa faz vira registro, e o estado
corrente da semana é sempre a proposta original mais a lista de ajustes.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from enum import StrEnum

from pydantic import Field, model_validator

from domain.planning.entities import (
    AvailabilitySlot,
    CapacityAssessment,
    ContractModel,
    EnrichedOperation,
    PlanningRequest,
    PlanningSnapshot,
    ScheduleAssignment,
    SchedulingSolution,
    TimeWindow,
    UnscheduledOperation,
    _ensure_aware,
)
from domain.planning.enums import UnscheduledReason


class AdjustmentKind(StrEnum):
    MOVE = "move"
    REMOVE = "remove"
    INCLUDE = "include"


class ScheduleAdjustment(ContractModel):
    sequence: int = Field(ge=1)
    kind: AdjustmentKind
    operation_id: str = Field(min_length=1)
    target_date: date | None = None
    target_worker_id: str | None = None
    reason: str | None = None
    applied_by: str = Field(min_length=1)
    applied_at: datetime

    @model_validator(mode="after")
    def destination_matches_kind(self) -> ScheduleAdjustment:
        # O fuso é incondicional: vale para os três tipos, antes de qualquer
        # ramificação por `kind`.
        _ensure_aware(self.applied_at)
        if self.kind is AdjustmentKind.REMOVE:
            if self.target_date is not None or self.target_worker_id is not None:
                raise ValueError("remove adjustments carry no destination")
            return self
        has_destination = self.target_date is not None and self.target_worker_id is not None
        is_partial_destination = (self.target_date is None) != (self.target_worker_id is None)
        if is_partial_destination or not has_destination:
            raise ValueError("move and include adjustments need day and worker")
        return self


def _align_up(moment: datetime, slot_minutes: int) -> datetime:
    if slot_minutes <= 0:
        return moment
    step = timedelta(minutes=slot_minutes)
    base = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = moment - base
    steps = -(-elapsed // step)  # divisão de teto
    return base + steps * step


def _on_day(window: TimeWindow, day: date) -> bool:
    return window.start.date() == day or window.end.date() == day


def fit_window(
    *,
    worker_id: str,
    day: date,
    minutes: int,
    availability: Sequence[AvailabilitySlot],
    busy: Sequence[TimeWindow],
    slot_minutes: int,
    tz: tzinfo,
) -> TimeWindow:
    """Primeiro intervalo livre da escala; se nada couber, estoura de propósito.

    Recusar o ajuste daria veto ao verificador, e ele não tem veto: o bloco entra
    depois do último compromisso e a violação aparece na conferência.
    """

    duration = timedelta(minutes=max(1, minutes))
    shifts = sorted(
        (
            slot.window
            for slot in availability
            if slot.worker_id == worker_id and _on_day(slot.window, day)
        ),
        key=lambda window: window.start,
    )
    committed = sorted(
        (window for window in busy if _on_day(window, day)),
        key=lambda window: window.start,
    )

    for shift in shifts:
        cursor = _align_up(shift.start, slot_minutes)
        for busy_window in committed:
            if busy_window.end <= cursor or busy_window.start >= shift.end:
                continue
            if busy_window.start - cursor >= duration:
                return TimeWindow(start=cursor, end=cursor + duration)
            cursor = max(cursor, _align_up(busy_window.end, slot_minutes))
        if shift.end - cursor >= duration:
            return TimeWindow(start=cursor, end=cursor + duration)

    if committed:
        start = _align_up(committed[-1].end, slot_minutes)
    elif shifts:
        start = _align_up(shifts[0].start, slot_minutes)
    else:
        start = datetime.combine(day, time.min, tzinfo=tz)
    return TimeWindow(start=start, end=start + duration)


def apply_adjustments(
    solution: SchedulingSolution,
    adjustments: Sequence[ScheduleAdjustment],
    snapshot: PlanningSnapshot,
    enriched: Sequence[EnrichedOperation],
    request: PlanningRequest,
    *,
    slot_minutes: int = 15,
    default_minutes: int = 60,
) -> SchedulingSolution:
    """Reaplica os ajustes sobre a proposta original, em ordem de sequência.

    A proposta do agente nunca é mutada: cada ajuste opera sobre dicionários de
    trabalho derivados dela e o retorno é uma solução nova. Ordenar por
    `sequence` (e não pela ordem de chegada da lista) é o que garante que duas
    listas com os mesmos ajustes produzam sempre a mesma solução — o que só
    vale se `sequence` for único; um valor repetido tornaria o resultado
    dependente da ordem de chegada, então é recusado antes de qualquer ajuste
    ser aplicado.
    """

    sequences_seen: set[int] = set()
    for adjustment in adjustments:
        if adjustment.sequence in sequences_seen:
            raise ValueError(f"duplicate sequence: {adjustment.sequence}")
        sequences_seen.add(adjustment.sequence)

    by_operation_id = {item.operation.operation_id: item for item in enriched}
    scheduled = {a.operation_id: a for a in solution.assignments}
    unscheduled = {u.operation_id: u for u in solution.unscheduled}
    # `request.period.start` sempre carrega fuso (validador de TimeWindow em
    # `entities.py`); o `or UTC` só estreita o tipo para o mypy, sem mudar o
    # valor de fato usado em tempo de execução.
    tz = request.period.start.tzinfo or UTC

    for adjustment in sorted(adjustments, key=lambda entry: entry.sequence):
        enriched_operation = by_operation_id.get(adjustment.operation_id)
        if enriched_operation is None:
            raise ValueError(f"operation is not in this run: {adjustment.operation_id}")

        if adjustment.kind is AdjustmentKind.REMOVE:
            if adjustment.operation_id not in scheduled:
                raise ValueError(f"operation is not scheduled: {adjustment.operation_id}")
            removed = scheduled.pop(adjustment.operation_id)
            unscheduled[adjustment.operation_id] = UnscheduledOperation(
                work_order_id=removed.work_order_id,
                operation_id=removed.operation_id,
                reason=UnscheduledReason.MANUAL,
                details=("MANUAL_REMOVAL",),
            )
            continue

        if adjustment.kind is AdjustmentKind.MOVE and adjustment.operation_id not in scheduled:
            raise ValueError(f"operation is not scheduled: {adjustment.operation_id}")
        if adjustment.kind is AdjustmentKind.INCLUDE and adjustment.operation_id in scheduled:
            raise ValueError(f"operation is already scheduled: {adjustment.operation_id}")

        assert adjustment.target_worker_id is not None
        assert adjustment.target_date is not None
        busy = [
            a.window
            for a in scheduled.values()
            if adjustment.target_worker_id in a.worker_ids
            and a.operation_id != adjustment.operation_id
        ]
        window = fit_window(
            worker_id=adjustment.target_worker_id,
            day=adjustment.target_date,
            minutes=enriched_operation.duration.minutes or default_minutes,
            availability=snapshot.availability,
            busy=busy,
            slot_minutes=slot_minutes,
            tz=tz,
        )
        previous = scheduled.get(adjustment.operation_id)
        priority_score = (
            previous.priority_score if previous is not None else enriched_operation.priority.score
        )
        scheduled[adjustment.operation_id] = ScheduleAssignment(
            work_order_id=enriched_operation.operation.work_order_id,
            operation_id=adjustment.operation_id,
            worker_ids=(adjustment.target_worker_id,),
            window=window,
            priority_score=priority_score,
            reason_codes=("MANUAL_ADJUSTMENT",),
        )
        unscheduled.pop(adjustment.operation_id, None)

    return solution.model_copy(
        update={
            "assignments": tuple(
                sorted(scheduled.values(), key=lambda a: (a.window.start, a.operation_id))
            ),
            "unscheduled": tuple(sorted(unscheduled.values(), key=lambda u: u.operation_id)),
        }
    )


class PlanningConstraints(ContractModel):
    """Restrições que a próxima montagem deve respeitar antes de otimizar.

    `must_include` é pré-alocação: fica declarado aqui como parte do contrato,
    mas quem o aplica é o serviço da tarefa 6, não `apply_constraints`. Os
    outros três campos são os filtros desta tarefa.
    """

    must_include: tuple[str, ...] = ()
    must_exclude: tuple[str, ...] = ()
    blocked_days: tuple[date, ...] = ()
    worker_asset_blocks: tuple[tuple[str, str], ...] = ()


def apply_constraints(
    enriched: Sequence[EnrichedOperation],
    capacities: Sequence[CapacityAssessment],
    constraints: PlanningConstraints,
    request: PlanningRequest,
) -> tuple[tuple[EnrichedOperation, ...], tuple[CapacityAssessment, ...]]:
    """Filtra as entradas do otimizador sem tocar no otimizador.

    Os três filtros agem sobre o que entra em `optimize_schedule`, nunca sobre
    o algoritmo em si: `must_exclude` tira operações do backlog considerado,
    `worker_asset_blocks` tira só o candidato bloqueado da lista de
    executantes de cada operação (sem descartar a operação nem mexer nos
    demais candidatos), e `blocked_days` tira os slots livres daquele dia da
    capacidade, descontando os minutos correspondentes de `gross_minutes` e
    `net_minutes` (sem tocar em `committed_minutes`, que não muda com o corte
    de slots livres). Sem nenhuma restrição, as entradas voltam inalteradas —
    é o caminho de toda execução que não usa restrição.
    """

    excluded = set(constraints.must_exclude)
    blocks = set(constraints.worker_asset_blocks)
    blocked_days = set(constraints.blocked_days)

    filtered: list[EnrichedOperation] = []
    for item in enriched:
        if item.operation.operation_id in excluded:
            continue
        if blocks and item.operation.asset_id is not None:
            candidates = tuple(
                candidate
                for candidate in item.executants
                if (candidate.worker_id, item.operation.asset_id) not in blocks
            )
            if candidates != item.executants:
                item = item.model_copy(update={"executants": candidates})
        filtered.append(item)

    if not blocked_days:
        return tuple(filtered), tuple(capacities)

    adjusted: list[CapacityAssessment] = []
    for capacity in capacities:
        slots = tuple(
            slot for slot in capacity.slots if slot.window.start.date() not in blocked_days
        )
        removed_minutes = sum(
            int((slot.window.end - slot.window.start).total_seconds() // 60)
            for slot in capacity.slots
            if slot.window.start.date() in blocked_days
        )
        adjusted.append(
            capacity.model_copy(
                update={
                    "slots": slots,
                    "gross_minutes": max(0, capacity.gross_minutes - removed_minutes),
                    "net_minutes": max(0, capacity.net_minutes - removed_minutes),
                }
            )
        )
    return tuple(filtered), tuple(adjusted)
