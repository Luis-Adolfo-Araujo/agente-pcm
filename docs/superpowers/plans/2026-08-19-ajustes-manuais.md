# Ajustes manuais da programação semanal — plano de implementação

> **Para trabalhadores agênticos:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar tarefa a tarefa. Os passos usam caixas (`- [ ]`) para acompanhamento.

**Objetivo:** permitir que o PCM ajuste a semana proposta pelo agente — mover, tirar e incluir ordens, e gravar regras para a próxima montagem — com o mesmo verificador conferindo a mão humana e toda mudança registrada.

**Arquitetura:** a proposta do agente é imutável. Cada ajuste é um registro tipado; o estado corrente é `apply_adjustments(proposta, ajustes)`, função pura com replay determinístico. Depois de cada ajuste, `verify_schedule` roda sobre a solução resultante e a API devolve solução, ajustes e verificação juntas. Restrições são uma camada separada, aplicada antes do otimizador na próxima montagem.

**Stack:** Python 3.11 + pydantic v2 (domínio e serviço), FastAPI (API), pytest (testes), Next.js 15 + React 19 + TypeScript (front).

## Restrições globais

- Spec de referência: `docs/superpowers/specs/2026-08-19-ajustes-manuais-programacao-design.md`. Ele manda; onde este plano e o spec divergirem, o spec vence.
- `pcm-agent` é repositório git na branch `ux-piloto-fase-1`; cada tarefa de backend termina em commit. `maia-web` **não** é repositório: lá o fechamento de tarefa é `npm run typecheck && npm run build` mais o detector, sem commit.
- Portões do repositório: `.venv/bin/python -m pytest tests`, `.venv/bin/python -m ruff check src tests` **e** `.venv/bin/python -m mypy src tests`. Os três antes de cada commit — o mypy é gate documentado no README e estava limpo antes desta feature.
- Identificadores em inglês; docstrings e comentários em português, como o restante do domínio já faz. O plano traz trechos de código com nomes locais em português: traduza-os ao implementar.
- Todo modelo novo herda `ContractModel` (de `domain/planning/entities`), que é o pydantic base do projeto — imutável e com validação estrita.
- Toda `datetime` carrega fuso. `_ensure_aware` já existe em `domain/planning/entities`.
- O otimizador não pode mudar: `algorithm_version` continua `greedy-v1` e o replay bit a bit dos testes existentes tem que seguir passando.
- O verificador não ganha exceção para mão humana: `verify_schedule(solution, snapshot, enriched, request)` é chamado igual, sem parâmetro de bypass.
- Textos de interface em português do Brasil, minúsculas em rótulo de dado, verbo que confirma a ação ("mover" → "movida"). Nunca "editar".
- Nenhuma escrita na Tractian, em nenhuma tarefa. `dry_run=True` permanece obrigatório.
- Cor: o laranja `#E84910` é reservado à etapa atual do chevron. A marca de ajuste humano usa `--senai-azul-claro` com o corte diagonal de −12°, conforme `DESIGN.md`.

---

## Estrutura de arquivos

**Backend (`pcm-agent`)**

| Arquivo | Responsabilidade |
|---|---|
| `src/domain/planning/adjustments.py` (novo) | `AdjustmentKind`, `ScheduleAdjustment`, `PlanningConstraints`, `fit_window`, `apply_adjustments`, `apply_constraints` |
| `src/domain/planning/enums.py` (modificar) | acrescenta `UnscheduledReason.MANUAL` |
| `src/application/pilot/models.py` (modificar) | `RevisionState`, campos novos em `HumanDecision` do piloto |
| `src/application/pilot/store.py` (modificar) | persistência de ajustes e restrições |
| `src/application/pilot/service.py` (modificar) | `add_adjustment`, `undo_last_adjustment`, `get_revision`, `set_constraints`, decisão com revisão |
| `src/application/workflows/generate_schedule.py` (modificar) | aceita `constraints` |
| `src/api/app.py` (modificar) | endpoints novos |

**Front (`maia-web`)**

| Arquivo | Responsabilidade |
|---|---|
| `src/lib/api.ts` (modificar) | tipos e chamadas de ajuste, revisão e restrição |
| `src/components/stages/PorDia.tsx` (novo) | régua de dias, linhas de técnico, blocos, buraco |
| `src/components/stages/BlocoOrdem.tsx` (novo) | um bloco com menu de teclado e alvo de arrasto |
| `src/components/stages/PainelFora.tsx` (novo) | busca e inclusão |
| `src/components/stages/PainelRegras.tsx` (novo) | restrições e montar de novo |
| `src/components/stages/Semana.tsx` (modificar) | acrescenta a aba "Por dia" |
| `src/components/stages/Decidir.tsx` (modificar) | aprova uma revisão, com violações conhecidas |
| `src/app/globals.css` (modificar) | classes do trilho de dias, linha de técnico, bloco e barra de ajustes |

---

### Task 0: fechar o trabalho pendente na branch

**Arquivos:**
- Commit: `src/agent/trace/writer.py`, `src/application/workflows/generate_schedule.py`, `src/application/pilot/exports.py`, `src/presentation/privacy.py`, `tests/end_to_end/test_generate_schedule.py`, `tests/integration/test_pilot_service.py`, `tests/unit/presentation/test_privacy.py`, `docs/superpowers/specs/`

- [ ] **Passo 1: rodar a suíte inteira**

Rode: `.venv/bin/python -m pytest tests -q`
Esperado: tudo passa (240 testes na última execução).

- [ ] **Passo 2: conferir lint**

Rode: `.venv/bin/python -m ruff check src tests`
Esperado: `All checks passed!`

- [ ] **Passo 3: commit**

```bash
git add -A
git commit -m "feat: time each planning skill and keep candidate records whole"
```

---

### Task 1: motivo MANUAL e o registro de ajuste

**Arquivos:**
- Modificar: `src/domain/planning/enums.py`
- Criar: `src/domain/planning/adjustments.py`
- Testar: `tests/unit/domain/test_adjustments.py`

**Interfaces:**
- Consome: `ContractModel` de `domain.planning.entities`.
- Produz: `AdjustmentKind` (StrEnum: `MOVE="move"`, `REMOVE="remove"`, `INCLUDE="include"`); `ScheduleAdjustment(sequence: int, kind: AdjustmentKind, operation_id: str, target_date: date | None, target_worker_id: str | None, reason: str | None, applied_by: str, applied_at: datetime)`; `UnscheduledReason.MANUAL`.

- [ ] **Passo 1: escrever o teste que falha**

```python
# tests/unit/domain/test_adjustments.py
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from domain.planning.adjustments import AdjustmentKind, ScheduleAdjustment
from domain.planning.enums import UnscheduledReason


def _ajuste(**overrides: object) -> ScheduleAdjustment:
    base: dict[str, object] = {
        "sequence": 1,
        "kind": AdjustmentKind.MOVE,
        "operation_id": "op-1",
        "target_date": date(2026, 8, 19),
        "target_worker_id": "w-1",
        "applied_by": "ana",
        "applied_at": datetime(2026, 8, 19, 12, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return ScheduleAdjustment(**base)


def test_manual_is_an_unscheduled_reason() -> None:
    assert UnscheduledReason.MANUAL.value == "manual"


def test_move_requires_a_destination() -> None:
    with pytest.raises(ValidationError):
        _ajuste(target_worker_id=None)
    with pytest.raises(ValidationError):
        _ajuste(target_date=None)


def test_remove_refuses_a_destination() -> None:
    with pytest.raises(ValidationError):
        _ajuste(kind=AdjustmentKind.REMOVE)


def test_remove_needs_no_destination() -> None:
    ajuste = _ajuste(kind=AdjustmentKind.REMOVE, target_date=None, target_worker_id=None)
    assert ajuste.kind is AdjustmentKind.REMOVE


def test_applied_at_must_carry_a_timezone() -> None:
    with pytest.raises(ValidationError):
        _ajuste(applied_at=datetime(2026, 8, 19, 12, 0))


def test_sequence_starts_at_one() -> None:
    with pytest.raises(ValidationError):
        _ajuste(sequence=0)
```

- [ ] **Passo 2: rodar e ver falhar**

Rode: `.venv/bin/python -m pytest tests/unit/domain/test_adjustments.py -v`
Esperado: FALHA com `ModuleNotFoundError: No module named 'domain.planning.adjustments'`.

- [ ] **Passo 3: acrescentar o motivo ao enum**

Em `src/domain/planning/enums.py`, dentro de `class UnscheduledReason`, acrescente a última linha:

```python
    OUTSIDE_PERIOD = "outside_period"
    MANUAL = "manual"
```

- [ ] **Passo 4: escrever o modelo**

```python
# src/domain/planning/adjustments.py
"""Ajustes que o PCM aplica sobre uma proposta já montada.

A proposta do agente é imutável: o que a pessoa faz vira registro, e o estado
corrente da semana é sempre a proposta original mais a lista de ajustes.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import Field, model_validator

from domain.planning.entities import ContractModel, _ensure_aware


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
        tem_destino = self.target_date is not None and self.target_worker_id is not None
        se_destino_parcial = (self.target_date is None) != (self.target_worker_id is None)
        if self.kind is AdjustmentKind.REMOVE:
            if self.target_date is not None or self.target_worker_id is not None:
                raise ValueError("remove adjustments carry no destination")
            return self
        if se_destino_parcial or not tem_destino:
            raise ValueError("move and include adjustments need day and worker")
        _ensure_aware(self.applied_at)
        return self
```

Se `_ensure_aware` não estiver exportado em `entities.py`, use a validação direta:
`if self.applied_at.tzinfo is None or self.applied_at.utcoffset() is None: raise ValueError("applied_at must include a timezone")` — e não altere `entities.py`.

- [ ] **Passo 5: rodar e ver passar**

Rode: `.venv/bin/python -m pytest tests/unit/domain/test_adjustments.py -v`
Esperado: 6 testes passam.

- [ ] **Passo 6: rodar a suíte inteira**

Rode: `.venv/bin/python -m pytest tests -q`
Esperado: nada quebrou — o enum ganhou um valor, ninguém perdeu um.

- [ ] **Passo 7: commit**

```bash
git add src/domain/planning/adjustments.py src/domain/planning/enums.py tests/unit/domain/test_adjustments.py
git commit -m "feat: record a manual schedule adjustment as a typed event"
```

---

### Task 2: encaixar a janela de horário

**Arquivos:**
- Modificar: `src/domain/planning/adjustments.py`
- Testar: `tests/unit/domain/test_encaixe.py`

**Interfaces:**
- Consome: `AvailabilitySlot(worker_id, window)`, `TimeWindow(start, end)`, `ScheduleAssignment` de `domain.planning.entities`.
- Produz: `fit_window(worker_id: str, dia: date, minutos: int, availability: Sequence[AvailabilitySlot], busy: Sequence[TimeWindow], slot_minutes: int, tz: tzinfo) -> TimeWindow`.

Regra: primeiro intervalo livre da escala daquele executante naquele dia, alinhado à granularidade. Quando não couber em nenhum, devolve uma janela que começa no fim do último compromisso do dia (ou no início da primeira escala, se não houver compromisso) — deliberadamente estourando a escala, para o verificador acusar.

- [ ] **Passo 1: escrever o teste que falha**

```python
# tests/unit/domain/test_encaixe.py
from datetime import UTC, date, datetime, timedelta

from domain.planning.adjustments import fit_window
from domain.planning.entities import AvailabilitySlot, TimeWindow


def _janela(h1: int, h2: int) -> TimeWindow:
    return TimeWindow(
        start=datetime(2026, 8, 19, h1, tzinfo=UTC),
        end=datetime(2026, 8, 19, h2, tzinfo=UTC),
    )


def _escala() -> list[AvailabilitySlot]:
    return [AvailabilitySlot(worker_id="w-1", window=_janela(8, 16))]


def test_fits_at_the_start_of_an_empty_shift() -> None:
    janela = fit_window(
        worker_id="w-1", dia=date(2026, 8, 19), minutos=120,
        availability=_escala(), busy=[], slot_minutes=15, tz=UTC,
    )
    assert janela.start == datetime(2026, 8, 19, 8, tzinfo=UTC)
    assert janela.end == datetime(2026, 8, 19, 10, tzinfo=UTC)


def test_takes_the_first_gap_after_committed_work() -> None:
    janela = fit_window(
        worker_id="w-1", dia=date(2026, 8, 19), minutos=60,
        availability=_escala(), busy=[_janela(8, 11)],
        slot_minutes=15, tz=UTC,
    )
    assert janela.start == datetime(2026, 8, 19, 11, tzinfo=UTC)


def test_aligns_to_the_slot_grid() -> None:
    ocupada = TimeWindow(
        start=datetime(2026, 8, 19, 8, tzinfo=UTC),
        end=datetime(2026, 8, 19, 8, 50, tzinfo=UTC),
    )
    janela = fit_window(
        worker_id="w-1", dia=date(2026, 8, 19), minutos=60,
        availability=_escala(), busy=[ocupada],
        slot_minutes=15, tz=UTC,
    )
    assert janela.start == datetime(2026, 8, 19, 9, tzinfo=UTC)


def test_overflows_the_shift_when_nothing_fits() -> None:
    janela = fit_window(
        worker_id="w-1", dia=date(2026, 8, 19), minutos=180,
        availability=_escala(), busy=[_janela(8, 15)],
        slot_minutes=15, tz=UTC,
    )
    assert janela.start == datetime(2026, 8, 19, 15, tzinfo=UTC)
    assert janela.end == datetime(2026, 8, 19, 18, tzinfo=UTC)
    assert janela.end > _escala()[0].window.end


def test_without_any_shift_starts_at_the_day_and_overflows() -> None:
    janela = fit_window(
        worker_id="w-1", dia=date(2026, 8, 19), minutos=60,
        availability=[], busy=[], slot_minutes=15, tz=UTC,
    )
    assert janela.start == datetime(2026, 8, 19, 0, tzinfo=UTC)
    assert janela.end - janela.start == timedelta(minutes=60)
```

- [ ] **Passo 2: rodar e ver falhar**

Rode: `.venv/bin/python -m pytest tests/unit/domain/test_encaixe.py -v`
Esperado: FALHA com `ImportError: cannot import name 'fit_window'`.

- [ ] **Passo 3: implementar**

Acrescente ao fim de `src/domain/planning/adjustments.py`:

```python
from collections.abc import Sequence
from datetime import time, timedelta, tzinfo

from domain.planning.entities import AvailabilitySlot, TimeWindow


def _align_up(momento: datetime, slot_minutes: int) -> datetime:
    if slot_minutes <= 0:
        return momento
    passo = timedelta(minutes=slot_minutes)
    base = momento.replace(hour=0, minute=0, second=0, microsecond=0)
    decorrido = momento - base
    passos = -(-decorrido // passo)  # teto
    return base + passos * passo


def _on_day(janela: TimeWindow, dia: date) -> bool:
    return janela.start.date() == dia or janela.end.date() == dia


def fit_window(
    *,
    worker_id: str,
    dia: date,
    minutos: int,
    availability: Sequence[AvailabilitySlot],
    busy: Sequence[TimeWindow],
    slot_minutes: int,
    tz: tzinfo,
) -> TimeWindow:
    """Primeiro intervalo livre da escala; se nada couber, estoura de propósito.

    Recusar o ajuste daria veto ao verificador, e ele não tem veto: o bloco entra
    depois do último compromisso e a violação aparece na conferência.
    """

    duracao = timedelta(minutes=max(1, minutos))
    escalas = sorted(
        (slot.window for slot in availability
         if slot.worker_id == worker_id and _on_day(slot.window, dia)),
        key=lambda janela: janela.start,
    )
    comprometidas = sorted(
        (janela for janela in busy if _on_day(janela, dia)),
        key=lambda janela: janela.start,
    )

    for escala in escalas:
        cursor = _align_up(escala.start, slot_minutes)
        for ocupada in comprometidas:
            if ocupada.end <= cursor or ocupada.start >= escala.end:
                continue
            if ocupada.start - cursor >= duracao:
                return TimeWindow(start=cursor, end=cursor + duracao)
            cursor = max(cursor, _align_up(ocupada.end, slot_minutes))
        if escala.end - cursor >= duracao:
            return TimeWindow(start=cursor, end=cursor + duracao)

    if comprometidas:
        inicio = _align_up(comprometidas[-1].end, slot_minutes)
    elif escalas:
        inicio = _align_up(escalas[0].start, slot_minutes)
    else:
        inicio = datetime.combine(dia, time.min, tzinfo=tz)
    return TimeWindow(start=inicio, end=inicio + duracao)
```

- [ ] **Passo 4: rodar e ver passar**

Rode: `.venv/bin/python -m pytest tests/unit/domain/test_encaixe.py -v`
Esperado: 5 testes passam.

- [ ] **Passo 5: commit**

```bash
git add src/domain/planning/adjustments.py tests/unit/domain/test_encaixe.py
git commit -m "feat: place a manually moved order in the first free slot"
```

---

### Task 3: aplicar os ajustes (replay determinístico)

**Arquivos:**
- Modificar: `src/domain/planning/adjustments.py`
- Testar: `tests/unit/domain/test_aplicar_ajustes.py`

**Interfaces:**
- Consome: `fit_window` (tarefa 2), `ScheduleAdjustment` (tarefa 1), `SchedulingSolution`, `ScheduleAssignment`, `UnscheduledOperation`, `EnrichedOperation`, `PlanningSnapshot`, `PlanningRequest`.
- Produz: `apply_adjustments(solution, adjustments, snapshot, enriched, request, slot_minutes=15, default_minutes=60) -> SchedulingSolution`.

Regras, na ordem:
- ajustes são aplicados por `sequence` crescente; a mesma lista sempre produz a mesma solução;
- `MOVE` exige a operação alocada; `REMOVE` idem; `INCLUDE` exige a operação fora. Violar isso levanta `ValueError` com a razão (a API traduz em 409);
- `MOVE` e `INCLUDE` marcam `reason_codes=("MANUAL_ADJUSTMENT",)` na alocação resultante, para o rastro sobreviver ao JSON;
- `REMOVE` devolve a operação a `unscheduled` com `reason=UnscheduledReason.MANUAL` e `details=("MANUAL_REMOVAL",)`;
- a duração vem de `enriched[op].duration.minutes`, caindo em `default_minutes` quando `None`;
- `status`, `objective_value` e `algorithm_version` da solução não mudam — quem os recalcula é o otimizador, e ele não rodou.

- [ ] **Passo 1: escrever o teste que falha**

```python
# tests/unit/domain/test_aplicar_ajustes.py
from datetime import UTC, date, datetime

import pytest

from domain.planning.adjustments import AdjustmentKind, ScheduleAdjustment, apply_adjustments
from domain.planning.enums import UnscheduledReason

from tests.support.planning import solucao_base, snapshot_base, enriched_base, request_base


def _ajuste(seq: int, kind: AdjustmentKind, op: str, dia=None, quem=None) -> ScheduleAdjustment:
    return ScheduleAdjustment(
        sequence=seq, kind=kind, operation_id=op,
        target_date=dia, target_worker_id=quem,
        applied_by="ana", applied_at=datetime(2026, 8, 19, 12, tzinfo=UTC),
    )


def test_move_changes_worker_and_day() -> None:
    resultado = apply_adjustments(
        solucao_base(), [_ajuste(1, AdjustmentKind.MOVE, "op-high", date(2026, 8, 20), "w-2")],
        snapshot_base(), enriched_base(), request_base(),
    )
    alocada = next(a for a in resultado.assignments if a.operation_id == "op-high")
    assert alocada.worker_ids == ("w-2",)
    assert alocada.window.start.date() == date(2026, 8, 20)
    assert "MANUAL_ADJUSTMENT" in alocada.reason_codes


def test_remove_sends_the_order_back_with_a_manual_reason() -> None:
    resultado = apply_adjustments(
        solucao_base(), [_ajuste(1, AdjustmentKind.REMOVE, "op-high")],
        snapshot_base(), enriched_base(), request_base(),
    )
    assert all(a.operation_id != "op-high" for a in resultado.assignments)
    fora = next(u for u in resultado.unscheduled if u.operation_id == "op-high")
    assert fora.reason is UnscheduledReason.MANUAL
    assert fora.details == ("MANUAL_REMOVAL",)


def test_include_brings_an_unscheduled_order_in() -> None:
    resultado = apply_adjustments(
        solucao_base(), [_ajuste(1, AdjustmentKind.INCLUDE, "op-out", date(2026, 8, 19), "w-1")],
        snapshot_base(), enriched_base(), request_base(),
    )
    assert any(a.operation_id == "op-out" for a in resultado.assignments)
    assert all(u.operation_id != "op-out" for u in resultado.unscheduled)


def test_replay_is_deterministic() -> None:
    ajustes = [
        _ajuste(1, AdjustmentKind.REMOVE, "op-high"),
        _ajuste(2, AdjustmentKind.INCLUDE, "op-out", date(2026, 8, 19), "w-1"),
    ]
    primeiro = apply_adjustments(solucao_base(), ajustes, snapshot_base(), enriched_base(), request_base())
    segundo = apply_adjustments(solucao_base(), list(reversed(ajustes)), snapshot_base(), enriched_base(), request_base())
    assert primeiro == segundo


def test_moving_an_unscheduled_order_is_refused() -> None:
    with pytest.raises(ValueError, match="not scheduled"):
        apply_adjustments(
            solucao_base(), [_ajuste(1, AdjustmentKind.MOVE, "op-out", date(2026, 8, 19), "w-1")],
            snapshot_base(), enriched_base(), request_base(),
        )


def test_including_a_scheduled_order_is_refused() -> None:
    with pytest.raises(ValueError, match="already scheduled"):
        apply_adjustments(
            solucao_base(), [_ajuste(1, AdjustmentKind.INCLUDE, "op-high", date(2026, 8, 19), "w-1")],
            snapshot_base(), enriched_base(), request_base(),
        )
```

- [ ] **Passo 2: criar as fixtures compartilhadas**

Crie `tests/support/__init__.py` vazio e `tests/support/planning.py` com quatro construtores mínimos: `snapshot_base()` com dois trabalhadores (`w-1`, `w-2`) ativos, escala das 8h às 16h nos dias 19 e 20/08/2026 e três operações (`op-high`, `op-medium`, `op-out`); `enriched_base()` com duração de 60 min para cada uma; `request_base()` com período de 18 a 25/08/2026, `dry_run=True`; `solucao_base()` com `op-high` e `op-medium` alocadas para `w-1` no dia 19 e `op-out` em `unscheduled` com `reason=UnscheduledReason.NO_CAPACITY`.

Copie a forma dos objetos de `tests/end_to_end/test_generate_schedule.py`, que já monta um snapshot completo — não invente campos.

- [ ] **Passo 3: rodar e ver falhar**

Rode: `.venv/bin/python -m pytest tests/unit/domain/test_aplicar_ajustes.py -v`
Esperado: FALHA com `ImportError: cannot import name 'apply_adjustments'`.

- [ ] **Passo 4: implementar**

Acrescente a `src/domain/planning/adjustments.py`:

```python
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
    """Reaplica os ajustes sobre a proposta original, em ordem de sequência."""

    por_id = {item.operation.operation_id: item for item in enriched}
    alocadas = {a.operation_id: a for a in solution.assignments}
    fora = {u.operation_id: u for u in solution.unscheduled}
    tz = request.period.start.tzinfo

    for ajuste in sorted(adjustments, key=lambda item: item.sequence):
        item = por_id.get(ajuste.operation_id)
        if item is None:
            raise ValueError(f"operation is not in this run: {ajuste.operation_id}")

        if ajuste.kind is AdjustmentKind.REMOVE:
            if ajuste.operation_id not in alocadas:
                raise ValueError(f"operation is not scheduled: {ajuste.operation_id}")
            removida = alocadas.pop(ajuste.operation_id)
            fora[ajuste.operation_id] = UnscheduledOperation(
                work_order_id=removida.work_order_id,
                operation_id=removida.operation_id,
                reason=UnscheduledReason.MANUAL,
                details=("MANUAL_REMOVAL",),
            )
            continue

        if ajuste.kind is AdjustmentKind.MOVE and ajuste.operation_id not in alocadas:
            raise ValueError(f"operation is not scheduled: {ajuste.operation_id}")
        if ajuste.kind is AdjustmentKind.INCLUDE and ajuste.operation_id in alocadas:
            raise ValueError(f"operation is already scheduled: {ajuste.operation_id}")

        assert ajuste.target_worker_id is not None and ajuste.target_date is not None
        busy = [
            a.window for a in alocadas.values()
            if ajuste.target_worker_id in a.worker_ids and a.operation_id != ajuste.operation_id
        ]
        janela = fit_window(
            worker_id=ajuste.target_worker_id,
            dia=ajuste.target_date,
            minutos=item.duration.minutes or default_minutes,
            availability=snapshot.availability,
            busy=busy,
            slot_minutes=slot_minutes,
            tz=tz,
        )
        anterior = alocadas.get(ajuste.operation_id)
        alocadas[ajuste.operation_id] = ScheduleAssignment(
            work_order_id=item.operation.work_order_id,
            operation_id=ajuste.operation_id,
            worker_ids=(ajuste.target_worker_id,),
            window=janela,
            priority_score=anterior.priority_score if anterior else item.priority.score,
            reason_codes=("MANUAL_ADJUSTMENT",),
        )
        fora.pop(ajuste.operation_id, None)

    return solution.model_copy(update={
        "assignments": tuple(sorted(alocadas.values(), key=lambda a: (a.window.start, a.operation_id))),
        "unscheduled": tuple(sorted(fora.values(), key=lambda u: u.operation_id)),
    })
```

Acrescente aos imports do módulo: `SchedulingSolution`, `ScheduleAssignment`, `UnscheduledOperation`, `EnrichedOperation`, `PlanningSnapshot`, `PlanningRequest` de `domain.planning.entities`, e `UnscheduledReason` de `domain.planning.enums`.

- [ ] **Passo 5: rodar e ver passar**

Rode: `.venv/bin/python -m pytest tests/unit/domain/test_aplicar_ajustes.py -v`
Esperado: 6 testes passam. O de replay é o que importa: ordenar por `sequence` faz duas listas embaralhadas produzirem a mesma solução.

- [ ] **Passo 6: commit**

```bash
git add src/domain/planning/adjustments.py tests/unit/domain/test_aplicar_ajustes.py tests/support/
git commit -m "feat: replay manual adjustments over the agent proposal"
```

---

### Task 4: restrições da próxima montagem

**Arquivos:**
- Modificar: `src/domain/planning/adjustments.py`, `src/application/workflows/generate_schedule.py`
- Testar: `tests/unit/domain/test_restricoes.py`

**Interfaces:**
- Produz: `PlanningConstraints(must_include: tuple[str, ...], must_exclude: tuple[str, ...], blocked_days: tuple[date, ...], worker_asset_blocks: tuple[tuple[str, str], ...])` e `apply_constraints(enriched, capacities, constraints, request) -> tuple[tuple[EnrichedOperation, ...], tuple[CapacityAssessment, ...]]`.
- `generate_schedule` ganha o parâmetro nomeado `constraints: PlanningConstraints | None = None`, aplicado logo antes de `optimize_schedule`.

- [ ] **Passo 1: escrever o teste que falha**

```python
# tests/unit/domain/test_restricoes.py
from datetime import date

from domain.planning.adjustments import PlanningConstraints, apply_constraints

from tests.support.planning import capacidades_base, enriched_base, request_base


def test_empty_constraints_change_nothing() -> None:
    enriched, capacidades = apply_constraints(
        enriched_base(), capacidades_base(), PlanningConstraints(), request_base()
    )
    assert enriched == enriched_base()
    assert capacidades == capacidades_base()


def test_must_exclude_drops_the_operation() -> None:
    enriched, _ = apply_constraints(
        enriched_base(), capacidades_base(),
        PlanningConstraints(must_exclude=("op-high",)), request_base(),
    )
    assert all(item.operation.operation_id != "op-high" for item in enriched)


def test_blocked_day_removes_that_day_from_capacity() -> None:
    _, capacidades = apply_constraints(
        enriched_base(), capacidades_base(),
        PlanningConstraints(blocked_days=(date(2026, 8, 19),)), request_base(),
    )
    for capacidade in capacidades:
        assert all(slot.window.start.date() != date(2026, 8, 19) for slot in capacidade.slots)


def test_worker_asset_block_removes_that_candidate() -> None:
    enriched, _ = apply_constraints(
        enriched_base(), capacidades_base(),
        PlanningConstraints(worker_asset_blocks=(("w-1", "asset-1"),)), request_base(),
    )
    alvo = next(item for item in enriched if item.operation.asset_id == "asset-1")
    assert all(candidato.worker_id != "w-1" for candidato in alvo.executants)
```

- [ ] **Passo 2: rodar e ver falhar**

Rode: `.venv/bin/python -m pytest tests/unit/domain/test_restricoes.py -v`
Esperado: FALHA com `ImportError: cannot import name 'PlanningConstraints'`.

- [ ] **Passo 3: implementar `PlanningConstraints` e `apply_constraints`**

`must_include` **não** entra em `apply_constraints`: ele é pré-alocação, e mora na tarefa 6 junto do serviço. Aqui ficam os três filtros:

```python
class PlanningConstraints(ContractModel):
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
    """Filtra entradas do otimizador sem tocar no otimizador."""

    excluidas = set(constraints.must_exclude)
    bloqueios = set(constraints.worker_asset_blocks)
    dias = set(constraints.blocked_days)

    filtrado: list[EnrichedOperation] = []
    for item in enriched:
        if item.operation.operation_id in excluidas:
            continue
        if bloqueios and item.operation.asset_id is not None:
            candidatos = tuple(
                candidato for candidato in item.executants
                if (candidato.worker_id, item.operation.asset_id) not in bloqueios
            )
            if candidatos != item.executants:
                item = item.model_copy(update={"executants": candidatos})
        filtrado.append(item)

    if not dias:
        return tuple(filtrado), tuple(capacities)

    ajustadas: list[CapacityAssessment] = []
    for capacidade in capacities:
        slots = tuple(slot for slot in capacidade.slots if slot.window.start.date() not in dias)
        removidos = sum(
            int((slot.window.end - slot.window.start).total_seconds() // 60)
            for slot in capacidade.slots if slot.window.start.date() in dias
        )
        ajustadas.append(capacidade.model_copy(update={
            "slots": slots,
            "gross_minutes": max(0, capacidade.gross_minutes - removidos),
            "net_minutes": max(0, capacidade.net_minutes - removidos),
        }))
    return tuple(filtrado), tuple(ajustadas)
```

- [ ] **Passo 4: ligar no workflow**

Em `src/application/workflows/generate_schedule.py`, acrescente `constraints: PlanningConstraints | None = None` à assinatura de `generate_schedule` e, imediatamente antes de `solution = optimize_schedule(enriched, capacities, request, config.optimizer)`:

```python
    enriched_para_otimizar, capacidades_para_otimizar = (
        apply_constraints(enriched, capacities, constraints, request)
        if constraints is not None
        else (enriched, capacities)
    )
```

e passe as duas variáveis novas para `optimize_schedule`. O `enriched` completo continua indo para o `PlanningRunResult` e para `verify_schedule` — restrição não some com a ordem do backlog, ela só a tira da otimização.

- [ ] **Passo 5: rodar e ver passar**

Rode: `.venv/bin/python -m pytest tests/unit/domain/test_restricoes.py tests/end_to_end -v`
Esperado: os 4 novos passam e os e2e continuam passando — sem `constraints`, o caminho é idêntico ao de antes.

- [ ] **Passo 6: commit**

```bash
git add src/domain/planning/adjustments.py src/application/workflows/generate_schedule.py tests/unit/domain/test_restricoes.py
git commit -m "feat: constrain the next planning run without touching the optimizer"
```

---

### Task 5: persistir ajustes e restrições

**Arquivos:**
- Modificar: `src/application/pilot/store.py`
- Testar: `tests/unit/application/test_pilot_store_ajustes.py`

`models.py` **não** entra: ajustes e restrições vivem em colunas próprias e são lidos pelo serviço direto do store, sem passar por campo de `PilotRun`. As Tarefas 6, 7 e 8 confirmam isso.

**Interfaces:**
- Produz, em `SQLitePilotStore`: `append_adjustment(run_id: str, adjustment: ScheduleAdjustment) -> tuple[ScheduleAdjustment, ...]`, `pop_last_adjustment(run_id: str) -> tuple[ScheduleAdjustment, ...]`, `list_adjustments(run_id: str) -> tuple[ScheduleAdjustment, ...]`, `save_constraints(run_id: str, constraints: PlanningConstraints) -> None`, `get_constraints(run_id: str) -> PlanningConstraints`.
- Migração: acrescentar as colunas `adjustments_json` e `constraints_json` a `pilot_runs`, com `ALTER TABLE` idempotente no `initialize()` (o projeto não usa framework de migração; siga o padrão que já existe em `initialize`).

- [ ] **Passo 1: escrever o teste que falha**

```python
# tests/unit/application/test_pilot_store_ajustes.py
from datetime import UTC, date, datetime
from pathlib import Path

from application.pilot.store import SQLitePilotStore
from domain.planning.adjustments import AdjustmentKind, PlanningConstraints, ScheduleAdjustment

from tests.support.planning import run_base


def _store(tmp_path: Path) -> SQLitePilotStore:
    store = SQLitePilotStore(tmp_path / "pilot.sqlite3")
    store.initialize()
    return store


def _ajuste(seq: int) -> ScheduleAdjustment:
    return ScheduleAdjustment(
        sequence=seq, kind=AdjustmentKind.REMOVE, operation_id=f"op-{seq}",
        applied_by="ana", applied_at=datetime(2026, 8, 19, 12, tzinfo=UTC),
    )


def test_adjustments_start_empty(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run = run_base()
    store.create_run(run)
    assert store.list_adjustments(run.run_id) == ()


def test_append_keeps_order(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run = run_base()
    store.create_run(run)
    store.append_adjustment(run.run_id, _ajuste(1))
    ajustes = store.append_adjustment(run.run_id, _ajuste(2))
    assert [a.sequence for a in ajustes] == [1, 2]


def test_pop_last_removes_only_the_last(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run = run_base()
    store.create_run(run)
    store.append_adjustment(run.run_id, _ajuste(1))
    store.append_adjustment(run.run_id, _ajuste(2))
    assert [a.sequence for a in store.pop_last_adjustment(run.run_id)] == [1]


def test_constraints_round_trip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run = run_base()
    store.create_run(run)
    store.save_constraints(run.run_id, PlanningConstraints(must_include=("op-1",), blocked_days=(date(2026, 8, 21),)))
    guardadas = store.get_constraints(run.run_id)
    assert guardadas.must_include == ("op-1",)
    assert guardadas.blocked_days == (date(2026, 8, 21),)
```

- [ ] **Passo 2: rodar e ver falhar**

Rode: `.venv/bin/python -m pytest tests/unit/application/test_pilot_store_ajustes.py -v`
Esperado: FALHA com `AttributeError: 'SQLitePilotStore' object has no attribute 'list_adjustments'`.

- [ ] **Passo 3: implementar no store**

Siga o padrão dos métodos existentes (`save_decision`, `update_progress`): serialize com `model_dump(mode="json")`, guarde como texto JSON na coluna, e reidrate com `model_validate`. `append_adjustment` lê a lista, acrescenta com `sequence = len(atual) + 1` (ignorando o `sequence` que veio, para a numeração ser do servidor) e grava. `pop_last_adjustment` remove o de maior `sequence`.

- [ ] **Passo 4: rodar e ver passar**

Rode: `.venv/bin/python -m pytest tests/unit/application -v`
Esperado: os 4 novos passam e os antigos do store continuam passando.

- [ ] **Passo 5: commit**

```bash
git add src/application/pilot/store.py src/application/pilot/models.py tests/unit/application/test_pilot_store_ajustes.py
git commit -m "feat: persist adjustments and constraints next to the run"
```

---

### Task 6: revisão no serviço, com verificação

**Arquivos:**
- Modificar: `src/application/pilot/service.py`
- Testar: `tests/integration/test_pilot_ajustes.py`

**Interfaces:**
- Produz: `PilotService.get_revision(run_id) -> dict`, `add_adjustment(run_id, *, kind, operation_id, target_date, target_worker_id, reason, applied_by) -> dict`, `undo_last_adjustment(run_id) -> dict`, `set_constraints(run_id, constraints) -> PlanningConstraints`.
- O `dict` da revisão tem a forma: `{"run_id", "revision_sequence": int, "adjustments": [...], "solution": {...}, "verification": {...}, "created_violations": [...], "inherited_violations": [...]}` — todos já serializados com `model_dump(mode="json")`, porque a API só faz `_clean` em cima.

Regras:
- `revision_sequence` é `len(adjustments)`; zero significa a proposta do agente sem mão humana;
- a verificação roda sobre a solução ajustada, com o mesmo `verify_schedule(solucao, snapshot, enriched, request)`, snapshot vindo de `self._catalog.get(run.snapshot_id)`;
- violação criada é a que existe na verificação da revisão e não existia na verificação original, comparando por `(code, operation_id)`.

`must_include` **não** entra aqui: a pré-alocação é lógica de montagem e tem tarefa própria (Task 17), que precisa estar pronta antes da Task 15.

- [ ] **Passo 1: escrever o teste que falha**

```python
# tests/integration/test_pilot_ajustes.py
from datetime import date

from domain.planning.adjustments import AdjustmentKind


def test_revision_starts_at_zero(service_com_run) -> None:
    service, run_id = service_com_run
    revisao = service.get_revision(run_id)
    assert revisao["revision_sequence"] == 0
    assert revisao["adjustments"] == []
    assert revisao["created_violations"] == []


def test_adjustment_bumps_the_revision_and_reverifies(service_com_run) -> None:
    service, run_id = service_com_run
    alocada = service.get_schedule(run_id)["assignments"][0]
    revisao = service.add_adjustment(
        run_id, kind=AdjustmentKind.REMOVE, operation_id=alocada["operation_id"],
        target_date=None, target_worker_id=None, reason="parada de linha", applied_by="ana",
    )
    assert revisao["revision_sequence"] == 1
    assert any(u["operation_id"] == alocada["operation_id"] for u in revisao["solution"]["unscheduled"])
    assert "verification" in revisao


def test_undo_returns_to_the_previous_revision(service_com_run) -> None:
    service, run_id = service_com_run
    alocada = service.get_schedule(run_id)["assignments"][0]
    service.add_adjustment(
        run_id, kind=AdjustmentKind.REMOVE, operation_id=alocada["operation_id"],
        target_date=None, target_worker_id=None, reason=None, applied_by="ana",
    )
    revisao = service.undo_last_adjustment(run_id)
    assert revisao["revision_sequence"] == 0
    assert any(a["operation_id"] == alocada["operation_id"] for a in revisao["solution"]["assignments"])


def test_overloading_a_worker_creates_a_violation(service_com_run) -> None:
    service, run_id = service_com_run
    agenda = service.get_schedule(run_id)
    alvo = agenda["assignments"][0]
    dia = date.fromisoformat(alvo["window"]["start"][:10])
    revisao = service.add_adjustment(
        run_id, kind=AdjustmentKind.MOVE, operation_id=agenda["assignments"][-1]["operation_id"],
        target_date=dia, target_worker_id=alvo["worker_ids"][0], reason=None, applied_by="ana",
    )
    assert revisao["revision_sequence"] == 1
    assert isinstance(revisao["created_violations"], list)
```

Use a fixture `service_com_run` de `tests/integration/test_pilot_service.py` (extraia para `conftest.py` se ainda for local ao módulo) — ela já monta serviço, snapshot e run completa.

- [ ] **Passo 2: rodar e ver falhar**

Rode: `.venv/bin/python -m pytest tests/integration/test_pilot_ajustes.py -v`
Esperado: FALHA com `AttributeError: 'PilotService' object has no attribute 'get_revision'`.

- [ ] **Passo 3: implementar no serviço**

Escreva um método privado `_revisao(run_id)` que carrega `_result(run_id)`, a lista de ajustes do store e o snapshot do catálogo; aplica `apply_adjustments`; roda `verify_schedule` duas vezes (proposta original e revisão) e monta o dicionário. Os quatro métodos públicos são cascas finas sobre ele: `add_adjustment` valida e grava antes, `undo_last_adjustment` remove antes, `get_revision` só lê, `set_constraints` grava e devolve.

`ValueError` levantado por `apply_adjustments` deve subir sem tratamento — a API traduz em 409.

- [ ] **Passo 4: rodar e ver passar**

Rode: `.venv/bin/python -m pytest tests/integration -v`
Esperado: os 4 novos passam, os antigos seguem.

- [ ] **Passo 5: commit**

```bash
git add src/application/pilot/service.py tests/integration/test_pilot_ajustes.py
git commit -m "feat: expose an adjusted revision, verified like the agent's own"
```

---

### Task 7: a decisão passa a aprovar uma revisão

**Arquivos:**
- Modificar: `src/application/pilot/models.py`, `src/application/pilot/service.py`, `src/application/pilot/store.py`
- Testar: `tests/integration/test_pilot_decisao_revisao.py`

**Interfaces:**
- `PilotRun.decision` ganha dois campos: `revision_sequence: int = 0` e `known_violations: tuple[dict[str, Any], ...] = ()`.
- `record_decision` ganha os parâmetros nomeados `revision_sequence: int` e devolve 409 (via `ValueError`) quando ele não bate com a revisão corrente.

- [ ] **Passo 1: escrever o teste que falha**

```python
# tests/integration/test_pilot_decisao_revisao.py
import pytest

from domain.planning.adjustments import AdjustmentKind
from domain.planning.enums import DecisionType


def test_decision_records_the_revision_it_approved(service_com_run) -> None:
    service, run_id = service_com_run
    run = service.record_decision(
        run_id=run_id, decision=DecisionType.APPROVE, decided_by="ana",
        reason="conferida na reunião", revision_sequence=0,
    )
    assert run.decision is not None
    assert run.decision.revision_sequence == 0


def test_stale_revision_is_refused(service_com_run) -> None:
    service, run_id = service_com_run
    alocada = service.get_schedule(run_id)["assignments"][0]
    service.add_adjustment(
        run_id, kind=AdjustmentKind.REMOVE, operation_id=alocada["operation_id"],
        target_date=None, target_worker_id=None, reason=None, applied_by="ana",
    )
    with pytest.raises(ValueError, match="revision"):
        service.record_decision(
            run_id=run_id, decision=DecisionType.APPROVE, decided_by="ana",
            reason="aprovando o que eu vi", revision_sequence=0,
        )


def test_known_violations_are_recorded(service_com_run) -> None:
    service, run_id = service_com_run
    revisao = service.get_revision(run_id)
    run = service.record_decision(
        run_id=run_id, decision=DecisionType.APPROVE, decided_by="ana",
        reason="ok", revision_sequence=revisao["revision_sequence"],
    )
    assert run.decision is not None
    assert list(run.decision.known_violations) == revisao["verification"]["violations"]
```

- [ ] **Passo 2: rodar e ver falhar**

Rode: `.venv/bin/python -m pytest tests/integration/test_pilot_decisao_revisao.py -v`
Esperado: FALHA com `TypeError: record_decision() got an unexpected keyword argument 'revision_sequence'`.

- [ ] **Passo 3: implementar**

O piloto tem seu próprio modelo de decisão em `application/pilot/models.py` (não confundir com `HumanDecision` do domínio, que é o que vai para a proposta revisada). Acrescente os dois campos ao modelo do piloto, propague em `save_decision` do store e em `record_decision` do serviço, e levante `ValueError("stale revision: the week changed since you read it")` quando a sequência não bate.

- [ ] **Passo 4: rodar e ver passar**

Rode: `.venv/bin/python -m pytest tests -q`
Esperado: suíte inteira verde.

- [ ] **Passo 5: commit**

```bash
git add src/application/pilot/ tests/integration/test_pilot_decisao_revisao.py
git commit -m "feat: approve a specific revision, with its known violations"
```

---

### Task 8: endpoints

**Arquivos:**
- Modificar: `src/api/app.py`
- Testar: `tests/integration/test_api_ajustes.py`

**Interfaces:**

| Método | Rota | Corpo | Resposta |
|---|---|---|---|
| GET | `/api/runs/{id}/revision` | — | revisão |
| POST | `/api/runs/{id}/adjustments` | `AdjustmentBody` | revisão |
| DELETE | `/api/runs/{id}/adjustments/last` | — | revisão |
| POST | `/api/runs/{id}/constraints` | `ConstraintsBody` | restrições |

`AdjustmentBody`: `kind: str`, `operation_id: str`, `target_date: date | None`, `target_worker_id: str | None`, `reason: str | None`, `applied_by: str = Field(min_length=1)`.
`ConstraintsBody`: espelha `PlanningConstraints`.
`DecisionBody` ganha `revision_sequence: int = Field(ge=0)`.
`StartRunBody` ganha `constraints: ConstraintsBody | None = None`.

Todos os endpoints novos levam `dependencies=[Depends(require_access)]` e passam a resposta por `_clean`. `ValueError` do serviço vira `HTTPException(409, detail=str(error))`, seguindo o padrão de `_artifact`.

- [ ] **Passo 1: escrever o teste que falha**

```python
# tests/integration/test_api_ajustes.py
from fastapi.testclient import TestClient


def test_revision_endpoint_answers_zero_for_a_fresh_run(api_client_com_run) -> None:
    client, run_id = api_client_com_run
    resposta = client.get(f"/api/runs/{run_id}/revision")
    assert resposta.status_code == 200
    assert resposta.json()["revision_sequence"] == 0


def test_adjustment_endpoint_applies_and_returns_the_revision(api_client_com_run) -> None:
    client, run_id = api_client_com_run
    agenda = client.get(f"/api/runs/{run_id}/schedule").json()
    alvo = agenda["assignments"][0]["operation_id"]
    resposta = client.post(f"/api/runs/{run_id}/adjustments", json={
        "kind": "remove", "operation_id": alvo, "applied_by": "ana", "reason": "parada de linha",
    })
    assert resposta.status_code == 200
    assert resposta.json()["revision_sequence"] == 1


def test_moving_an_unscheduled_order_answers_409(api_client_com_run) -> None:
    client, run_id = api_client_com_run
    fora = client.get(f"/api/runs/{run_id}/schedule").json()["unscheduled"][0]["operation_id"]
    resposta = client.post(f"/api/runs/{run_id}/adjustments", json={
        "kind": "move", "operation_id": fora, "target_date": "2026-08-19",
        "target_worker_id": "w-1", "applied_by": "ana",
    })
    assert resposta.status_code == 409


def test_undo_endpoint_returns_to_the_previous_revision(api_client_com_run) -> None:
    client, run_id = api_client_com_run
    alvo = client.get(f"/api/runs/{run_id}/schedule").json()["assignments"][0]["operation_id"]
    client.post(f"/api/runs/{run_id}/adjustments", json={
        "kind": "remove", "operation_id": alvo, "applied_by": "ana",
    })
    resposta = client.delete(f"/api/runs/{run_id}/adjustments/last")
    assert resposta.status_code == 200
    assert resposta.json()["revision_sequence"] == 0


def test_constraints_round_trip(api_client_com_run) -> None:
    client, run_id = api_client_com_run
    resposta = client.post(f"/api/runs/{run_id}/constraints", json={
        "must_include": ["op-1"], "blocked_days": ["2026-08-21"],
    })
    assert resposta.status_code == 200
    assert resposta.json()["must_include"] == ["op-1"]
```

A fixture `api_client_com_run` monta `TestClient(create_app())` com `MAIA_PILOT_SNAPSHOT_DIR`/`MAIA_PILOT_RUN_DIR`/`MAIA_PILOT_DB` apontando para `tmp_path` e uma run completa — siga o padrão do teste de API que já existe.

- [ ] **Passo 2: rodar e ver falhar**

Rode: `.venv/bin/python -m pytest tests/integration/test_api_ajustes.py -v`
Esperado: FALHA com 404 em `/revision`.

- [ ] **Passo 3: implementar os endpoints**

- [ ] **Passo 4: rodar e ver passar**

Rode: `.venv/bin/python -m pytest tests -q && .venv/bin/python -m ruff check src tests`
Esperado: suíte verde e lint limpo.

- [ ] **Passo 5: commit**

```bash
git add src/api/app.py tests/integration/test_api_ajustes.py
git commit -m "feat: serve adjustments, revision and constraints over HTTP"
```

---

## Front — nota de método

`maia-web` não tem suíte de teste nem git. Cada tarefa fecha com o mesmo ritual, e ele substitui o "rodar o teste" das tarefas de backend:

```bash
cd maia-web
npm run typecheck && npm run build
node <caminho-do-impeccable>/scripts/detect.mjs --json src
```

Esperado: typecheck sem saída, build com `✓ Compiled successfully`, detector com `[]`.

Verificação de verdade é contra a API viva. Suba os dois antes de começar:

```bash
cd pcm-agent && PYTHONPATH=src .venv/bin/python -m uvicorn api.app:app --port 8001 &
cd maia-web && npm run dev
```

---

### Task 9: cliente da API

**Arquivos:**
- Modificar: `src/lib/api.ts`

**Interfaces:**
- Produz os tipos `AdjustmentKind = 'move' | 'remove' | 'include'`, `Adjustment`, `Constraints`, `Revision`, e em `api`: `revision(id)`, `adjust(id, body)`, `undoAdjustment(id)`, `setConstraints(id, body)`.

- [ ] **Passo 1: acrescentar os tipos**

```ts
export type AdjustmentKind = 'move' | 'remove' | 'include';

export type Adjustment = {
  sequence: number;
  kind: AdjustmentKind;
  operation_id: string;
  target_date: string | null;
  target_worker_id: string | null;
  reason: string | null;
  applied_by: string;
  applied_at: string;
};

export type Constraints = {
  must_include: string[];
  must_exclude: string[];
  blocked_days: string[];
  worker_asset_blocks: [string, string][];
};

export type Revision = {
  run_id: string;
  revision_sequence: number;
  adjustments: Adjustment[];
  solution: Schedule;
  verification: Verification;
  created_violations: Violation[];
  inherited_violations: Violation[];
};
```

- [ ] **Passo 2: acrescentar as chamadas ao objeto `api`**

```ts
  revision: (id: string) => get<Revision>(`/api/runs/${id}/revision`),
  adjust: (id: string, body: {
    kind: AdjustmentKind; operation_id: string;
    target_date?: string | null; target_worker_id?: string | null;
    reason?: string | null; applied_by: string;
  }) => post<Revision>(`/api/runs/${id}/adjustments`, body),
  undoAdjustment: (id: string) => del<Revision>(`/api/runs/${id}/adjustments/last`),
  setConstraints: (id: string, body: Partial<Constraints>) =>
    post<Constraints>(`/api/runs/${id}/constraints`, body),
```

`del` ainda não existe: escreva-o ao lado de `get`/`post`, com o mesmo `headers()`, `ApiError` e `method: 'DELETE'`.

- [ ] **Passo 3: acrescentar o rótulo do motivo manual**

Em `REASON_NAMES`, acrescente `manual: 'Tirada da semana pelo PCM'`.

- [ ] **Passo 4: fechar a tarefa** (ritual do front, acima)

---

### Task 10: vocabulário visual do trilho e do bloco

**Arquivos:**
- Modificar: `src/app/globals.css`

Traduza os quadros de `design/ajustes-manuais/` em classes. Os valores são os do canvas, que já saíram dos tokens do app — não invente novos:

- `.trilho-dias` — `display: flex; gap: 8px; padding: 16px 44px; border-bottom: 1px solid var(--color-border); overflow-x: auto`
- `.chip-dia` — `border-radius: var(--radius-md); padding: 10px 16px; min-width: 116px; text-align: center; background: var(--color-paper); border: 1px solid var(--color-border)`; `[data-estado='ativo']` usa `background: var(--senai-azul); color: #FFFFFF; border-color: var(--senai-azul)`; `[data-estado='alvo']` usa `background: var(--azul-100); border: 1px dashed var(--senai-azul)`
- `.linha-tecnico` — `border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: 14px 16px`; `[data-alvo='sim']` troca para `1px dashed var(--senai-azul)` e fundo `var(--azul-100)`; `[data-alvo='nao-cabe']` para `1px dashed var(--cinza-400)` e fundo `var(--color-paper)`
- `.carga` / `.carga > i` — barra de 170×6, trilho `var(--azul-100)`, preenchimento `var(--senai-azul)`; `[data-estourou='sim'] > i` em `var(--color-blocked)`
- `.bloco-ordem` — `border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 10px 12px; background: #FFFFFF; box-shadow: var(--shadow-sm); display: flex; gap: 12px; align-items: center; width: 100%; text-align: left; font: inherit; cursor: pointer`; `[data-estado='ajustado']` com borda `var(--senai-azul-claro)`; `[data-estado='violacao']` com borda `var(--color-blocked)` e fundo `#FCE9E7`; `[data-estado='arrastando']` com borda `var(--senai-azul)`, `box-shadow: var(--shadow-md)` e `transform: rotate(-1deg)`
- `.selo-ajuste` — pílula `background: var(--azul-100); color: var(--senai-azul)`, com `<i>` de 7px em `var(--senai-azul-claro)` e `transform: skewX(-12deg)`
- `.barra-ajustes` — `position: sticky; bottom: 0; border-top: 1px solid var(--color-border-strong); background: #FFFFFF; box-shadow: 0 -8px 24px rgba(14,27,51,.06); padding: 14px 44px; display: flex; align-items: center; gap: 20px`
- `.buraco` — `border: 1px dashed var(--cinza-400); border-radius: var(--radius-md); background: var(--color-paper); padding: 12px 14px`
- Grade do dia: `.grade-dia { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 20px; align-items: start }` e, em `max-width: 900px`, `grid-template-columns: minmax(0, 1fr)`
- Em `max-width: 640px`: `.bloco-ordem { min-height: 44px }` e o arrasto é desligado no componente, não no CSS

- [ ] **Passo 1: escrever as classes**
- [ ] **Passo 2: fechar a tarefa** (ritual do front)

---

### Task 11: a aba "Por dia", só leitura

> **Reordenada.** Esta tarefa foi adiantada para antes das Tasks 7, 8 e 17: a visão por dia é leitura de `schedule.assignments`, que a tela já baixa, e não depende de nenhuma API de ajuste. Enquanto `GET /revision` não existir, `PorDia` recebe `schedule` e `backlog` diretamente; quando existir, passa a receber `revision.solution` no lugar de `schedule`, sem mudar o resto.

**Arquivos:**
- Criar: `src/components/stages/PorDia.tsx`
- Modificar: `src/components/stages/Semana.tsx`, `src/app/page.tsx`

**Interfaces:**
- `PorDia({ run, revision, backlog, snapshot, onAjuste, onDesfazer, trabalhando })` onde `onAjuste(body)` e `onDesfazer()` sobem para `page.tsx`, que detém a revisão.
- `page.tsx` ganha o estado `revision: Revision | null`, carregado junto dos artefatos (`api.revision(run.run_id)`), e passa `revision` para `Semana`.

Nesta tarefa a tela só **mostra**: régua de dias derivada do período da run, linhas de técnico do dia selecionado, blocos ordenados por horário. Ajuste vem na tarefa 12.

- [ ] **Passo 1: derivar os dias e agrupar**

```ts
const dias = useMemo(() => {
  const inicio = new Date(run.request.period.start);
  const fim = new Date(run.request.period.end);
  const lista: string[] = [];
  for (let d = new Date(inicio); d < fim; d.setDate(d.getDate() + 1)) {
    lista.push(d.toISOString().slice(0, 10));
  }
  return lista;
}, [run]);

const porDiaETecnico = useMemo(() => {
  const mapa = new Map<string, Map<string, Assignment[]>>();
  revision.solution.assignments.forEach((a) => {
    const dia = a.window.start.slice(0, 10);
    const pessoas = mapa.get(dia) ?? new Map<string, Assignment[]>();
    a.worker_ids.forEach((w) => pessoas.set(w, [...(pessoas.get(w) ?? []), a]));
    mapa.set(dia, pessoas);
  });
  return mapa;
}, [revision]);
```

Atenção ao fuso: `a.window.start` vem com offset do snapshot; `slice(0, 10)` sobre a string ISO preserva o dia local do dado, enquanto `new Date(...)` converteria para UTC e deslocaria — o mesmo defeito que `proximaSemana` tem em `Montar.tsx`.

- [ ] **Passo 2: ordenar as linhas por carga decrescente e congelar**

A ordem é recalculada **quando o dia muda**, não a cada ajuste: guarde `ordemTecnicos` em `useState` e recalcule dentro de um `useEffect` que depende só de `dia`. Bloco que pula debaixo do cursor é defeito.

- [ ] **Passo 3: renderizar régua, linhas e blocos**

Carga do técnico: some `(fim − início)` das alocações dele no dia; a escala vem de `backlog.capacities.find(c => c.worker_id === w)?.gross_minutes` dividido pelo número de dias com escala — se a API não der a escala por dia, mostre `Xh alocadas` sem denominador em vez de inventar um.

- [ ] **Passo 4: ligar como terceira aba da etapa 3**

Em `Semana.tsx`, acrescente `{ id: 'dia', rotulo: 'Por dia' }` como **primeira** aba, com o `TabPanel` correspondente. As abas "Na semana" e "Fora da semana" continuam.

- [ ] **Passo 5: conferir contra a API viva**

Abra a etapa 3, aba "Por dia", e confira três coisas contra `curl /api/runs/{id}/schedule`: a soma de ordens por dia bate com a régua; um técnico específico tem os mesmos horários; o total de blocos da semana é igual a `assignments.length`.

- [ ] **Passo 6: fechar a tarefa** (ritual do front)

---

### Task 12: ajustar pelo menu, com barra e faixa de violação

**Arquivos:**
- Criar: `src/components/stages/BlocoOrdem.tsx`
- Modificar: `src/components/stages/PorDia.tsx`, `src/app/page.tsx`

**Interfaces:**
- `BlocoOrdem({ assignment, titulo, dias, tecnicos, estado, onMover, onTirar, onExplicar })`.
- `page.tsx` ganha `aplicarAjuste(body)` e `desfazerAjuste()`, que chamam `api.adjust` / `api.undoAdjustment`, guardam a `Revision` devolvida e tratam `ApiError` 409 com a mensagem de sessão desatualizada.

- [ ] **Passo 1: o bloco vira botão com menu**

`<button className="bloco-ordem">` com `aria-haspopup="menu"`; Enter e Espaço abrem o menu; Escape fecha e devolve o foco ao bloco. O menu é `role="menu"` com quatro itens: **Mover para outro dia** (submenu com os dias), **Mover para outro técnico** (submenu com busca e a carga de cada um), **Tirar da semana**, **Por que esta ordem entrou** (leva à etapa 4).

- [ ] **Passo 2: anunciar cada ajuste**

Em `PorDia.tsx`, uma região `aria-live="polite"` recebe a frase depois de cada aplicação: `Inspeção no sistema pneumático movida para quarta, Técnico-C6CBD5B6, 14h30. Nenhuma violação nova.` Quando houver violação criada, use `role="alert"` e diga quantas.

- [ ] **Passo 3: barra de ajustes**

Só existe quando `revision.revision_sequence > 0`: `N ajustes seus`, contagem de violações criadas, e os botões **Desfazer último** e **Ver todos** (lista em `<details>` com tipo, ordem, destino, quem e quando).

- [ ] **Passo 4: faixa de violação criada**

Abaixo da régua, `data-tone="bad"`, listando `created_violations` com `code`, `details` e a OS, mais **Desfazer este ajuste** e **Manter assim mesmo** (que só fecha a faixa). Violações herdadas ficam fora dessa faixa — elas já existiam e não são notícia deste ajuste.

- [ ] **Passo 5: conferir contra a API viva**

Mova uma ordem para um técnico já cheio e confirme que a faixa aparece com `CAPACITY_EXCEEDED`; desfaça e confirme que a revisão volta a zero.

- [ ] **Passo 6: fechar a tarefa** (ritual do front)

---

### Task 13: arrastar

**Arquivos:**
- Modificar: `src/components/stages/BlocoOrdem.tsx`, `src/components/stages/PorDia.tsx`

Use a API nativa de arrasto do HTML (`draggable`, `dragstart`, `dragover`, `drop`) — sem biblioteca. Os quatro alvos, exatamente como no spec: outra linha de técnico (mover no mesmo dia), chip da régua (mover de dia), painel "fora da semana" (tirar), e do painel para uma linha (incluir).

- [ ] **Passo 1: origem do arrasto**

`draggable={!estreito}` no bloco, onde `estreito` vem de `window.matchMedia('(max-width: 640px)')`. No `dragstart`, `event.dataTransfer.setData('text/plain', operation_id)` e marque o bloco com `data-estado="arrastando"`.

- [ ] **Passo 2: alvos**

Cada linha de técnico e cada chip de dia trata `dragover` (com `preventDefault`, senão o `drop` não dispara) e marca `data-alvo`. A linha calcula se a duração cabe na folga daquele técnico e mostra `não cabe · faltam Xh` — sem impedir o `drop`.

- [ ] **Passo 3: soltar**

O `drop` chama o mesmo `onMover`/`onTirar`/`onIncluir` do menu. Nenhum caminho novo de dados: arrasto e menu produzem o mesmo ajuste.

- [ ] **Passo 4: limpar sempre**

`dragend` limpa `data-estado` e `data-alvo` mesmo quando o arrasto é cancelado (Escape ou soltar fora) — estado grudado é o defeito clássico de arrasto feito à mão.

- [ ] **Passo 5: conferir**

Arraste entre técnicos, para um chip de dia e para o painel. Depois repita tudo pelo teclado, para confirmar que as duas vias produzem o mesmo resultado. Em 390px, confirme que `draggable` está desligado e o menu funciona.

- [ ] **Passo 6: fechar a tarefa** (ritual do front)

---

### Task 14: painel "fora da semana" e o buraco

**Arquivos:**
- Criar: `src/components/stages/PainelFora.tsx`
- Modificar: `src/components/stages/PorDia.tsx`

- [ ] **Passo 1: busca**

Campo único filtrando por `work_order_id` e por título, sem distinção de acento ou caixa (`localeCompare` com `sensitivity: 'base'`, ou `normalize('NFD').replace(/\p{Diacritic}/gu, '')`). Resultado ordenado por score, teto de 40 cartões com a contagem do que ficou de fora do teto. Vazio diz o que foi buscado e oferece limpar.

- [ ] **Passo 2: incluir**

Cada cartão tem "Incluir na semana", que pede dia e técnico (o mesmo submenu do bloco) e emite `INCLUDE`.

- [ ] **Passo 3: buraco e sugestões**

Na linha do técnico, calcule a maior folga contígua do dia. Quando for **≥ 60 min**, mostre `.buraco` com `Xh livres` e até três ordens de fora que caibam, ordenadas por score, cada uma com "Incluir aqui" — que já vem com dia e técnico preenchidos. O limiar é 60 min, do spec; não invente outro.

- [ ] **Passo 4: fechar a tarefa** (ritual do front)

---

### Task 15: regras e montar de novo

**Arquivos:**
- Criar: `src/components/stages/PainelRegras.tsx`
- Modificar: `src/components/stages/Montar.tsx`, `src/app/page.tsx`

- [ ] **Passo 1: listar e editar regras**

Quatro tipos, cada um com sua forma de acrescentar: ordem que precisa entrar, ordem que não entra (ambas por busca de OS), técnico bloqueado para um ativo (dois seletores), dia travado (chip da régua). Cada regra tem "remover".

- [ ] **Passo 2: montar de novo**

O botão chama `api.startRun` com `constraints`. Quando houver ajustes na revisão corrente, abra antes uma confirmação que diz quantos ajustes serão perdidos e oferece **converter em regras** — `MOVE` e `INCLUDE` viram `must_include`, `REMOVE` vira `must_exclude`.

- [ ] **Passo 3: fechar a tarefa** (ritual do front)

---

### Task 16: a decisão aprova a revisão que está na tela

**Arquivos:**
- Modificar: `src/components/stages/Decidir.tsx`, `src/app/page.tsx`

- [ ] **Passo 1: resumo antes dos botões**

Acima dos campos, mostre o que está sendo decidido: período, ordens alocadas, pessoas envolvidas, cobertura, número de ajustes humanos e de violações em pé. A garantia "aprovar não publica programação, não altera OS e não escreve na Tractian" sobe para **antes** do botão, em tamanho de corpo.

- [ ] **Passo 2: mandar a revisão**

`api.decide` passa a enviar `revision_sequence: revision.revision_sequence`. Um 409 mostra "A semana mudou desde que você abriu esta tela" com botão para recarregar a revisão — nunca aprovar em cima do desconhecido.

- [ ] **Passo 3: aprovar com violação**

Quando `verification.violations.length > 0`, o botão de aprovar continua habilitado, mas o rótulo passa a **Aprovar mesmo com N violações** e o campo de motivo vira obrigatório com um mínimo de 20 caracteres — a decisão precisa carregar a justificativa.

- [ ] **Passo 4: fechar a tarefa** (ritual do front)

- [ ] **Passo 5: rodar a vistoria de novo**

Rode `/impeccable critique maia-web/src/components/stages/PorDia.tsx` e compare com a linha de base de 16/40 registrada em `.impeccable/critique/`.

---

## Autorrevisão do plano

**Cobertura do spec:** modelo de ajuste (T1), encaixe (T2), replay (T3), restrições (T4), persistência (T5), verificação e revisão (T6), decisão auditada (T7), API (T8), cliente (T9), vocabulário visual (T10), tela por dia (T11), menu e barra (T12), arrasto (T13), busca e buraco (T14), regras (T15), decisão na tela (T16). Os nove estados da seção "Estados" do spec estão distribuídos entre T11, T12 e T14; acessibilidade em T12 e T13; responsivo em T10 e T13.

**Consistência de nomes:** `apply_adjustments`, `fit_window`, `apply_constraints`, `PlanningConstraints`, `ScheduleAdjustment`, `AdjustmentKind`, `get_revision`, `add_adjustment`, `undo_last_adjustment`, `set_constraints`, `revision_sequence`, `known_violations`, `created_violations`, `inherited_violations` — usados com a mesma grafia em todas as tarefas e iguais aos do spec.

**Ponto de atenção conhecido:** a escala por dia de cada técnico não é servida hoje pela API (`capacities` traz só totais da semana). A T11 manda mostrar horas alocadas sem denominador nesse caso, em vez de inventar um. Se o denominador for necessário na tela, isso vira uma tarefa de backend própria — não improvise no front.


---

### Task 17: `must_include` pré-alocado na montagem

**Arquivos:**
- Modificar: `src/domain/planning/adjustments.py`, `src/application/workflows/generate_schedule.py`, `src/application/pilot/service.py`
- Testar: `tests/unit/domain/test_restricoes.py`, `tests/integration/test_pilot_ajustes.py`

**Interfaces:**
- Produz: `preallocate(enriched, capacities, constraints, snapshot, request, *, slot_minutes) -> tuple[tuple[ScheduleAssignment, ...], tuple[UnscheduledOperation, ...], tuple[CapacityAssessment, ...]]`.
- `generate_schedule` chama `preallocate` depois de `apply_constraints` e antes de `optimize_schedule`, junta as alocações reservadas ao resultado do otimizador, e subtrai da capacidade os slots que elas ocuparam.
- `PilotService.start_run` passa `constraints` adiante para o agente.

Regras:
- cada `operation_id` em `must_include` é alocado com `fit_window`, ao melhor executante elegível daquela ordem (maior `score` entre `executants` com `eligible=True`), no primeiro dia do período que tenha escala para ele;
- a ordem pré-alocada é removida do `enriched` que vai ao otimizador, e os minutos usados saem da capacidade daquele executante, para o otimizador não alocar duas coisas no mesmo horário;
- ordem exigida **sem executante elegível** não é forçada: entra em `unscheduled` com `reason=UnscheduledReason.MANUAL` e `details=("CONSTRAINT_MUST_INCLUDE_UNMET",)`. A regra que não pôde ser cumprida aparece; ela nunca mente sobre ter sido respeitada;
- `reason_codes` da alocação pré-alocada é `("CONSTRAINT_MUST_INCLUDE",)`, para a tela distinguir o que entrou por regra do que entrou por otimização.

- [ ] **Passo 1: escrever o teste que falha**

```python
# acrescente a tests/unit/domain/test_restricoes.py
from domain.planning.adjustments import PlanningConstraints, preallocate
from domain.planning.enums import UnscheduledReason

from tests.support.planning import capacities_base, enriched_base, request_base, snapshot_base


def test_must_include_reserves_the_order_before_the_optimizer() -> None:
    reserved, unmet, capacities = preallocate(
        enriched_base(), capacities_base(),
        PlanningConstraints(must_include=("op-out",)),
        snapshot_base(), request_base(), slot_minutes=15,
    )
    assert [item.operation_id for item in reserved] == ["op-out"]
    assert reserved[0].reason_codes == ("CONSTRAINT_MUST_INCLUDE",)
    assert unmet == ()


def test_reserved_minutes_leave_the_capacity() -> None:
    _, _, capacities = preallocate(
        enriched_base(), capacities_base(),
        PlanningConstraints(must_include=("op-out",)),
        snapshot_base(), request_base(), slot_minutes=15,
    )
    antes = {item.worker_id: item.net_minutes for item in capacities_base()}
    depois = {item.worker_id: item.net_minutes for item in capacities}
    assert sum(depois.values()) < sum(antes.values())


def test_a_rule_that_cannot_be_met_says_so() -> None:
    sem_candidato = tuple(
        item.model_copy(update={"executants": ()}) if item.operation.operation_id == "op-out" else item
        for item in enriched_base()
    )
    reserved, unmet, _ = preallocate(
        sem_candidato, capacities_base(),
        PlanningConstraints(must_include=("op-out",)),
        snapshot_base(), request_base(), slot_minutes=15,
    )
    assert reserved == ()
    assert [item.operation_id for item in unmet] == ["op-out"]
    assert unmet[0].reason is UnscheduledReason.MANUAL
    assert unmet[0].details == ("CONSTRAINT_MUST_INCLUDE_UNMET",)


def test_empty_must_include_reserves_nothing() -> None:
    reserved, unmet, capacities = preallocate(
        enriched_base(), capacities_base(), PlanningConstraints(),
        snapshot_base(), request_base(), slot_minutes=15,
    )
    assert reserved == ()
    assert unmet == ()
    assert capacities == capacities_base()
```

- [ ] **Passo 2: rodar e ver falhar**

Rode: `.venv/bin/python -m pytest tests/unit/domain/test_restricoes.py -v`
Esperado: FALHA com `ImportError: cannot import name 'preallocate'`.

- [ ] **Passo 3: implementar `preallocate`**

Reuse `fit_window` para a janela e a mesma aritmética de minutos que `apply_constraints` já usa para descontar capacidade. Não duplique regra de encaixe.

- [ ] **Passo 4: ligar no workflow e no serviço**

Em `generate_schedule`, depois de `apply_constraints`: chame `preallocate`, tire do `enriched` que vai ao otimizador as ordens reservadas, passe as capacidades reduzidas, e junte `reserved` às `assignments` e `unmet` às `unscheduled` da solução final — mantendo a ordenação determinística que a solução já tem. Em `PilotService.start_run`, aceite `constraints` e repasse.

- [ ] **Passo 5: rodar e ver passar**

Rode: `.venv/bin/python -m pytest tests -q && .venv/bin/python -m ruff check src tests && .venv/bin/python -m mypy src tests`
Esperado: os quatro novos passam, os e2e continuam idênticos (sem `constraints`, o caminho não muda).

- [ ] **Passo 6: commit**

```bash
git add src/domain/planning/adjustments.py src/application/workflows/generate_schedule.py src/application/pilot/service.py tests/unit/domain/test_restricoes.py
git commit -m "feat: reserve the orders a rule requires before optimizing"
```
