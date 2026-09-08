# Correções de UX do Piloto — Fase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir os defeitos de UX do piloto que independem da direção visual escolhida (A, B ou C), incluindo dois bugs que exibem dado errado na tela.

**Architecture:** As telas ficam em `src/presentation/pages.py` e recebem o objeto Streamlit por injeção, mas nunca foram testadas. A primeira tarefa cria um dublê de Streamlit que torna as telas testáveis; as demais corrigem defeitos com teste antes do código. Nenhuma tarefa altera o domínio nem o serviço.

**Tech Stack:** Python 3.11, Streamlit 1.61, pytest, ruff, mypy strict, pydantic v2.

## Global Constraints

- Toda produção de código segue TDD: teste falhando primeiro, verificado falhando, depois implementação mínima.
- `uv run pytest`, `uv run ruff check src tests` e `uv run mypy src tests` precisam passar ao fim de cada tarefa.
- `uv` não está no PATH da shell do usuário; use `.venv/bin/pytest`, `.venv/bin/ruff`, `.venv/bin/mypy` se `uv run` falhar.
- Nenhuma tarefa altera `src/domain/` nem `src/application/`.
- Nenhuma tarefa muda `proposal_id`, versões de skill ou qualquer contrato canônico.
- Textos de interface em português do Brasil, sem emoji.
- Ausência de dado nunca é exibida como valor: use rótulo explícito ("Não informada").

---

### Task 1: Dublê de Streamlit para tornar as telas testáveis

**Files:**
- Create: `tests/support/__init__.py`
- Create: `tests/support/fake_streamlit.py`
- Test: `tests/unit/presentation/test_fake_streamlit.py`

**Interfaces:**
- Consumes: nada.
- Produces: `FakeStreamlit` com atributos `session_state: dict[str, Any]`, `errors: list[str]`, `infos: list[str]`, `warnings: list[str]`, `captions: list[str]`, `metrics: list[tuple[str, Any]]`, `dataframes: list[Any]`, `buttons_clicked: set[str]`; e a exceção `StreamlitStopped`. Usado por todas as tarefas seguintes.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/presentation/test_fake_streamlit.py
from __future__ import annotations

import pytest

from tests.support.fake_streamlit import FakeStreamlit, StreamlitStopped


def test_metric_records_label_and_value() -> None:
    st = FakeStreamlit()

    st.metric("Operações", 1200)

    assert st.metrics == [("Operações", 1200)]


def test_columns_returns_independent_children_sharing_the_record() -> None:
    st = FakeStreamlit()

    first, second = st.columns(2)
    first.metric("A", 1)
    second.metric("B", 2)

    assert st.metrics == [("A", 1), ("B", 2)]


def test_selectbox_returns_the_indexed_option() -> None:
    st = FakeStreamlit()

    assert st.selectbox("Snapshot", ["a", "b"], index=1) == "b"


def test_stop_raises_so_the_page_aborts_like_streamlit() -> None:
    st = FakeStreamlit()

    with pytest.raises(StreamlitStopped):
        st.stop()


def test_unknown_widget_is_tolerated_and_returns_none() -> None:
    st = FakeStreamlit()

    assert st.balloons() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/presentation/test_fake_streamlit.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'tests.support'`

- [ ] **Step 3: Write minimal implementation**

```python
# tests/support/__init__.py
"""Utilitários compartilhados pelos testes."""
```

```python
# tests/support/fake_streamlit.py
"""Dublê de Streamlit para exercitar as telas sem navegador.

As telas recebem o objeto Streamlit por injeção, então um dublê que registra
o que foi desenhado é suficiente para testar a lógica de apresentação.
"""

from __future__ import annotations

import datetime
from typing import Any


class StreamlitStopped(Exception):
    """Equivale a ``st.stop()``: interrompe a renderização da página."""


class FakeStreamlit:
    def __init__(self, session_state: dict[str, Any] | None = None) -> None:
        self.session_state: dict[str, Any] = session_state if session_state is not None else {}
        self.errors: list[str] = []
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.captions: list[str] = []
        self.successes: list[str] = []
        self.metrics: list[tuple[str, Any]] = []
        self.dataframes: list[Any] = []
        self.buttons_clicked: set[str] = set()
        self._record = self

    def _child(self) -> FakeStreamlit:
        child = FakeStreamlit(self.session_state)
        child._record = self._record
        return child

    # Mensagens
    def error(self, body: Any = "", *args: Any, **kwargs: Any) -> None:
        self._record.errors.append(str(body))

    def info(self, body: Any = "", *args: Any, **kwargs: Any) -> None:
        self._record.infos.append(str(body))

    def warning(self, body: Any = "", *args: Any, **kwargs: Any) -> None:
        self._record.warnings.append(str(body))

    def caption(self, body: Any = "", *args: Any, **kwargs: Any) -> None:
        self._record.captions.append(str(body))

    def success(self, body: Any = "", *args: Any, **kwargs: Any) -> None:
        self._record.successes.append(str(body))

    def metric(self, label: Any = "", value: Any = None, *args: Any, **kwargs: Any) -> None:
        self._record.metrics.append((str(label), value))

    def dataframe(self, data: Any = None, *args: Any, **kwargs: Any) -> None:
        self._record.dataframes.append(data)

    # Widgets com retorno
    def selectbox(
        self,
        label: Any,
        options: Any,
        index: int = 0,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        items = list(options)
        return items[index] if items else None

    def radio(self, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        items = list(options)
        return items[0] if items else None

    def multiselect(self, label: Any, options: Any, *args: Any, **kwargs: Any) -> list[Any]:
        return []

    def checkbox(self, label: Any, value: bool = False, *args: Any, **kwargs: Any) -> bool:
        return value

    def number_input(self, label: Any, *args: Any, value: Any = 0, **kwargs: Any) -> Any:
        return value

    def text_input(self, label: Any, *args: Any, value: str = "", **kwargs: Any) -> str:
        return value

    def text_area(self, label: Any, *args: Any, value: str = "", **kwargs: Any) -> str:
        return value

    def date_input(
        self,
        label: Any,
        value: Any = None,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        return value if value is not None else datetime.date(2026, 8, 18)

    def button(self, label: Any = "", *args: Any, **kwargs: Any) -> bool:
        return str(label) in self._record.buttons_clicked

    def form_submit_button(self, label: Any = "", *args: Any, **kwargs: Any) -> bool:
        return str(label) in self._record.buttons_clicked

    def download_button(self, label: Any = "", *args: Any, **kwargs: Any) -> bool:
        return False

    # Layout
    def columns(self, spec: Any, *args: Any, **kwargs: Any) -> list[FakeStreamlit]:
        count = spec if isinstance(spec, int) else len(spec)
        return [self._child() for _ in range(count)]

    def tabs(self, labels: Any, *args: Any, **kwargs: Any) -> list[FakeStreamlit]:
        return [self._child() for _ in labels]

    def expander(self, *args: Any, **kwargs: Any) -> FakeStreamlit:
        return self

    def form(self, *args: Any, **kwargs: Any) -> FakeStreamlit:
        return self

    def spinner(self, *args: Any, **kwargs: Any) -> FakeStreamlit:
        return self

    def container(self, *args: Any, **kwargs: Any) -> FakeStreamlit:
        return self

    def __enter__(self) -> FakeStreamlit:
        return self

    def __exit__(self, *args: Any) -> bool:
        return False

    # Controle de fluxo
    def stop(self) -> None:
        raise StreamlitStopped()

    def rerun(self) -> None:
        raise StreamlitStopped()

    def fragment(self, *args: Any, **kwargs: Any) -> Any:
        def decorator(function: Any) -> Any:
            return function

        return decorator

    def __getattr__(self, name: str) -> Any:
        def anything(*args: Any, **kwargs: Any) -> None:
            return None

        return anything


__all__ = ["FakeStreamlit", "StreamlitStopped"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/presentation/test_fake_streamlit.py -v`
Expected: PASS (5 testes)

- [ ] **Step 5: Commit**

```bash
git add tests/support tests/unit/presentation/test_fake_streamlit.py
git commit -m "test: add fake Streamlit so pages become testable"
```

---

### Task 2: Contadores do snapshot deixam de aparecer como travessão

O bug: `snapshot_rows` procura `operation_count` no nível de cima do dicionário, mas `SnapshotSummary` os publica dentro de `quality`. A tela mostra `—` em Operações, Pessoas e Materiais.

**Files:**
- Modify: `src/presentation/view_models.py` (função `snapshot_rows`)
- Test: `tests/unit/presentation/test_view_models.py`

**Interfaces:**
- Consumes: `FakeStreamlit` da Task 1 (não usado nesta tarefa).
- Produces: `snapshot_rows` passa a ler `quality.operation_count`, `quality.worker_count` e `quality.inventory_item_count`.

- [ ] **Step 1: Write the failing test**

Acrescente ao fim de `tests/unit/presentation/test_view_models.py`:

```python
def test_snapshot_rows_read_counts_from_the_quality_block() -> None:
    """SnapshotSummary publica os contadores dentro de quality, não na raiz."""

    rows = snapshot_rows(
        [
            {
                "snapshot_id": "snap-1",
                "tenant_id": "planta-modelo",
                "as_of": "2026-08-17T12:00:00+00:00",
                "quality": {
                    "operation_count": 1200,
                    "worker_count": 22,
                    "inventory_item_count": 1800,
                },
            }
        ]
    )

    assert rows[0]["operações"] == 1200
    assert rows[0]["pessoas"] == 22
    assert rows[0]["materiais"] == 1800


def test_snapshot_rows_fall_back_to_not_informed_without_counts() -> None:
    rows = snapshot_rows([{"snapshot_id": "snap-1"}])

    assert rows[0]["operações"] == "Não informado"
```

E acrescente `snapshot_rows` ao import no topo do arquivo:

```python
from presentation.view_models import (
    backlog_rows,
    duration_rows,
    filter_backlog,
    material_rows,
    operation_detail,
    quality_rows,
    run_status_view,
    snapshot_rows,
    to_plain,
    trace_rows,
    unscheduled_rows,
    verification_view,
)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/presentation/test_view_models.py -k snapshot_rows -v`
Expected: FAIL com `assert '—' == 1200`

- [ ] **Step 3: Write minimal implementation**

Em `src/presentation/view_models.py`, substitua o corpo de `snapshot_rows` por:

```python
def snapshot_rows(snapshots: Iterable[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for snapshot in snapshots:
        item = _mapping(snapshot)
        metadata_value = item.get("metadata")
        metadata: dict[str, Any] = metadata_value if isinstance(metadata_value, dict) else {}
        quality_value = item.get("quality")
        quality: dict[str, Any] = quality_value if isinstance(quality_value, dict) else {}

        sources = (quality, item, metadata)

        def _count(*keys: str, lookup: tuple[dict[str, Any], ...] = sources) -> Any:
            for source in lookup:
                for key in keys:
                    value = source.get(key)
                    if isinstance(value, int) and not isinstance(value, bool):
                        return value
            return "Não informado"

        rows.append(
            {
                "snapshot_id": item.get("snapshot_id", item.get("id", "")),
                "tenant": item.get("tenant_id", item.get("tenant", "")),
                "data_corte": item.get("as_of", item.get("created_at", "")),
                "operações": _count("operation_count", "operations_total"),
                "pessoas": _count("worker_count", "workers_total"),
                "materiais": _count("inventory_item_count", "inventory_count", "inventory_total"),
            }
        )
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/presentation -v`
Expected: PASS, sem regressão nos testes existentes

- [ ] **Step 5: Commit**

```bash
git add src/presentation/view_models.py tests/unit/presentation/test_view_models.py
git commit -m "fix: read snapshot counts from the quality block"
```

---

### Task 3: Tela de configuração mostra o escopo real

Mesma causa da Task 2, segunda ocorrência: `pages.py` lê `metadata.operation_count` e exibe "Escopo informado pelo snapshot: **— operações**".

**Files:**
- Modify: `src/presentation/pages.py:311-317`
- Test: `tests/unit/presentation/test_configuration_page.py` (criar)

**Interfaces:**
- Consumes: `FakeStreamlit` (Task 1), `snapshot_rows` corrigido (Task 2).
- Produces: nada novo.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/presentation/test_configuration_page.py
from __future__ import annotations

from typing import Any

from presentation.pages import render_configuration_page
from presentation.service_adapter import PilotServiceAdapter
from tests.support.fake_streamlit import FakeStreamlit

SNAPSHOT = {
    "snapshot_id": "snap-1",
    "tenant_id": "planta-modelo",
    "as_of": "2026-08-17T12:00:00-03:00",
    "quality": {"operation_count": 1200, "worker_count": 22, "inventory_item_count": 1800},
}


class StubService:
    def list_snapshots(self) -> list[dict[str, Any]]:
        return [SNAPSHOT]

    def start_run(self, **kwargs: Any) -> dict[str, Any]:
        return {"run_id": "run-1", "status": "queued"}

    def get_run(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "queued"}

    def get_backlog(self, run_id: str) -> dict[str, Any]:
        return {}

    def get_schedule(self, run_id: str) -> dict[str, Any]:
        return {}

    def get_verification(self, run_id: str) -> dict[str, Any]:
        return {}

    def record_decision(self, **kwargs: Any) -> dict[str, Any]:
        return {}

    def record_feedback(self, **kwargs: Any) -> list[Any]:
        return []

    def export_run(self, **kwargs: Any) -> dict[str, Any]:
        return {}


def test_scope_shows_the_real_operation_count() -> None:
    st = FakeStreamlit({"selected_snapshot_id": "snap-1"})

    render_configuration_page(st, PilotServiceAdapter(StubService()))

    assert any("1200" in message or "1.200" in message for message in st.infos)
    assert not any("—" in message for message in st.infos)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/presentation/test_configuration_page.py -v`
Expected: FAIL — a mensagem contém `—` em vez de 1200

- [ ] **Step 3: Write minimal implementation**

Em `src/presentation/pages.py`, substitua o bloco das linhas 311-317 por:

```python
    counts = snapshot_rows([plain_snapshot])[0]
    st.info(f"Escopo informado pelo snapshot: **{counts['operações']} operações**.")
```

E acrescente `snapshot_rows` ao import existente de `presentation.view_models` (ele já está importado no arquivo; confirme que consta na lista).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/presentation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/presentation/pages.py tests/unit/presentation/test_configuration_page.py
git commit -m "fix: show the real operation count on the configuration screen"
```

---

### Task 4: Período padrão ancorado no corte do snapshot

Hoje o período vem de `date.today()`. O plano exige a primeira janela completa de sete dias posterior ao corte dos dados. Com um snapshot que envelhece, o padrão atual afasta a simulação dos dados sem avisar.

**Files:**
- Modify: `src/presentation/pages.py` (`_configuration_form` e `render_configuration_page`)
- Test: `tests/unit/presentation/test_configuration_page.py`

**Interfaces:**
- Consumes: `FakeStreamlit` (Task 1).
- Produces: `_configuration_form(st, *, as_of: datetime)` — a assinatura ganha o parâmetro obrigatório `as_of`.

- [ ] **Step 1: Write the failing test**

Acrescente a `tests/unit/presentation/test_configuration_page.py`:

```python
from datetime import date

from presentation.pages import default_period


def test_default_period_starts_the_day_after_the_snapshot_cut() -> None:
    start, end = default_period(date(2026, 8, 17))

    assert start == date(2026, 8, 18)
    assert end == date(2026, 8, 24)


def test_default_period_covers_seven_full_days() -> None:
    start, end = default_period(date(2026, 1, 31))

    assert (end - start).days == 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/presentation/test_configuration_page.py -k default_period -v`
Expected: FAIL com `ImportError: cannot import name 'default_period'`

- [ ] **Step 3: Write minimal implementation**

Em `src/presentation/pages.py`, acrescente antes de `_configuration_form`:

```python
def default_period(as_of_date: date) -> tuple[date, date]:
    """Primeira janela completa de sete dias após o corte dos dados.

    Ancorar no snapshot, e não no relógio, mantém a simulação perto dos dados
    mesmo quando o snapshot envelhece.
    """

    start = as_of_date + timedelta(days=1)
    return start, start + timedelta(days=6)
```

Troque a assinatura e as duas primeiras linhas de `_configuration_form`:

```python
def _configuration_form(st: Any, *, as_of_date: date) -> tuple[date, date, PlanningConfig, bool]:
    defaults = PlanningConfig()
    suggested_start, suggested_end = default_period(as_of_date)
    period_start = st.date_input("Início do período", value=suggested_start)
    period_end = st.date_input("Fim do período", value=suggested_end)
```

Remova a linha `today = date.today()`.

Em `render_configuration_page`, troque a chamada:

```python
    with st.form("planning-config"):
        period_start, period_end, config, submitted = _configuration_form(
            st, as_of_date=as_of.date()
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/presentation -v && uv run mypy src tests`
Expected: PASS e mypy limpo

- [ ] **Step 5: Commit**

```bash
git add src/presentation/pages.py tests/unit/presentation/test_configuration_page.py
git commit -m "fix: anchor the default period to the snapshot cut instead of today"
```

---

### Task 5: Telas dependentes deixam de ser beco sem saída

Sete das dez telas abortam com "Gere ou selecione uma simulação para acessar esta tela." sem indicar destino nem oferecer ação. É a causa direta de "não sei como começar".

**Files:**
- Modify: `src/presentation/pages.py` (`_active_run`)
- Test: `tests/unit/presentation/test_navigation.py` (criar)

**Interfaces:**
- Consumes: `FakeStreamlit` (Task 1).
- Produces: `_active_run` passa a escrever, em `st.session_state["pilot_page"]`, o rótulo `"Configuração e geração"` quando o usuário clica no botão de atalho.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/presentation/test_navigation.py
from __future__ import annotations

import pytest

from presentation.pages import _active_run
from tests.support.fake_streamlit import FakeStreamlit, StreamlitStopped


def test_a_screen_without_a_run_names_the_destination() -> None:
    st = FakeStreamlit()

    assert _active_run(st) is None
    assert any("Configuração e geração" in message for message in st.infos)


def test_the_shortcut_button_moves_the_user_to_the_configuration_screen() -> None:
    """O clique grava a página de destino e interrompe o ciclo, como st.rerun."""

    st = FakeStreamlit()
    st.buttons_clicked.add("Ir para Configuração e geração")

    with pytest.raises(StreamlitStopped):
        _active_run(st)

    assert st.session_state["pilot_page"] == "Configuração e geração"


def test_an_active_run_passes_through_untouched() -> None:
    st = FakeStreamlit({"active_run_id": "run-1"})

    assert _active_run(st) == "run-1"
    assert st.infos == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/presentation/test_navigation.py -v`
Expected: FAIL — a mensagem atual não cita a tela e não há botão

- [ ] **Step 3: Write minimal implementation**

Em `src/presentation/pages.py`, substitua `_active_run`:

```python
def _active_run(st: Any) -> str | None:
    identifier = st.session_state.get("active_run_id")
    if not identifier:
        st.info(
            "Esta tela mostra o resultado de uma simulação e ainda não existe uma. "
            "Comece em Configuração e geração."
        )
        if st.button("Ir para Configuração e geração", type="primary"):
            st.session_state["pilot_page"] = "Configuração e geração"
            st.rerun()
        return None
    return str(identifier)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/presentation -v`
Expected: PASS

Observação para o implementador: a navegação lateral em `pilot_app.py` usa `st.radio(..., key="pilot_page")`, então gravar `st.session_state["pilot_page"]` antes do `st.rerun()` move a seleção. Confirme essa chave antes de implementar; se ela tiver mudado, ajuste o nome nos dois lugares.

- [ ] **Step 5: Commit**

```bash
git add src/presentation/pages.py tests/unit/presentation/test_navigation.py
git commit -m "fix: give dependent screens a way forward instead of a dead end"
```

---

### Task 6: Progresso real da execução e remoção da estimativa errada

Duas correções na mesma tela: a copy diz "cerca de 47 segundos" quando a execução mede ~5 s, e a barra de progresso usa 10/55/100 fixos ignorando os seis estágios que o trace publica.

**Files:**
- Modify: `src/presentation/pages.py:356` e `render_execution_page`
- Test: `tests/unit/presentation/test_execution_progress.py` (criar)

**Interfaces:**
- Consumes: `trace_rows` de `presentation.view_models`.
- Produces: `execution_progress(run: Any) -> int` em `src/presentation/view_models.py`, devolvendo 0–100.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/presentation/test_execution_progress.py
from __future__ import annotations

from presentation.view_models import execution_progress

STAGES = [
    "snapshot_validated",
    "skills_parallel",
    "executant_candidates",
    "optimization",
    "verification",
    "proposal_ready",
]


def _run(status: str, stage_count: int) -> dict[str, object]:
    return {
        "status": status,
        "trace_events": [
            {"sequence": index + 1, "stage": STAGES[index], "elapsed_ms": 1.0, "counts": {}}
            for index in range(stage_count)
        ],
    }


def test_a_queued_run_has_not_started() -> None:
    assert execution_progress(_run("queued", 0)) == 0


def test_progress_follows_the_stages_actually_completed() -> None:
    assert execution_progress(_run("running", 3)) == 50


def test_a_completed_run_is_full_regardless_of_trace() -> None:
    assert execution_progress(_run("completed", 6)) == 100


def test_a_failed_run_keeps_the_progress_it_reached() -> None:
    assert execution_progress(_run("failed", 2)) == 33
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/presentation/test_execution_progress.py -v`
Expected: FAIL com `ImportError: cannot import name 'execution_progress'`

- [ ] **Step 3: Write minimal implementation**

Em `src/presentation/view_models.py`, acrescente antes de `run_status_view`:

```python
_PLANNING_STAGE_COUNT = 6


def execution_progress(run: Any) -> int:
    """Percentual derivado das etapas realmente concluídas, não de um chute."""

    status = str(_mapping(run).get("status", ""))
    if status in {"completed", "complete", "ready", "succeeded", "success"}:
        return 100
    completed = len(trace_rows(run))
    return min(100, round(completed / _PLANNING_STAGE_COUNT * 100))
```

Em `src/presentation/pages.py`, dentro de `render_execution_page`, substitua o dicionário `progress_by_status` e as duas linhas seguintes por:

```python
    st.metric("Estado", status_name.upper())
    st.progress(execution_progress(run))
```

Acrescente `execution_progress` ao import de `presentation.view_models` em `pages.py`.

Ainda em `pages.py`, substitua a linha 356:

```python
    st.info("Acompanhe o andamento pela tela Execução.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/presentation -v && uv run ruff check src tests && uv run mypy src tests`
Expected: PASS, ruff e mypy limpos

- [ ] **Step 5: Commit**

```bash
git add src/presentation/view_models.py src/presentation/pages.py tests/unit/presentation/test_execution_progress.py
git commit -m "fix: derive execution progress from real stages and drop the stale estimate"
```

---

### Task 7: Remover o ramo morto do Plotly

`render_schedule_page` captura `ModuleNotFoundError` e sugere instalar "o extra visual do piloto". Plotly está no mesmo extra `pilot` que traz o Streamlit: se a página renderiza, Plotly existe. A instrução é impossível de seguir e mascara um erro real caso apareça.

**Files:**
- Modify: `src/presentation/pages.py` (`render_schedule_page`)
- Test: `tests/unit/presentation/test_schedule_page.py` (criar)

**Interfaces:**
- Consumes: nada novo.
- Produces: nada novo.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/presentation/test_schedule_page.py
from __future__ import annotations

from typing import Any

from presentation.pages import render_schedule_page
from presentation.service_adapter import PilotServiceAdapter
from tests.support.fake_streamlit import FakeStreamlit

BACKLOG = {
    "backlog": [
        {
            "operation": {
                "work_order_id": "wo-1",
                "operation_id": "op-1",
                "title": "Inspecionar redutor",
                "planned_team_id": "mecanica",
                "location_id": "area-1",
                "asset_id": "asset-1",
            },
            "priority": {"score": 90.0, "components": [], "reason_codes": []},
            "duration": {"minutes": 60, "reason_codes": []},
            "materials": {"status": "available", "blocking": False, "reason_codes": []},
            "executants": [],
            "scheduled": True,
        }
    ]
}
SCHEDULE = {
    "assignments": [
        {
            "work_order_id": "wo-1",
            "operation_id": "op-1",
            "worker_ids": ["worker-1"],
            "window": {
                "start": "2026-08-18T08:00:00+00:00",
                "end": "2026-08-18T09:00:00+00:00",
            },
            "priority_score": 90.0,
            "reason_codes": ["PRIORITY_ORDER"],
        }
    ],
    "unscheduled": [],
}


class StubService:
    def get_run(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "completed"}

    def get_backlog(self, run_id: str) -> dict[str, Any]:
        return BACKLOG

    def get_schedule(self, run_id: str) -> dict[str, Any]:
        return SCHEDULE

    def list_snapshots(self) -> list[Any]:
        return []

    def start_run(self, **kwargs: Any) -> dict[str, Any]:
        return {}

    def get_verification(self, run_id: str) -> dict[str, Any]:
        return {}

    def record_decision(self, **kwargs: Any) -> dict[str, Any]:
        return {}

    def record_feedback(self, **kwargs: Any) -> list[Any]:
        return []

    def export_run(self, **kwargs: Any) -> dict[str, Any]:
        return {}


def test_the_schedule_page_renders_the_chart_without_an_install_notice() -> None:
    """Plotly vem no mesmo extra do Streamlit: se a tela roda, o gráfico existe."""

    st = FakeStreamlit({"active_run_id": "run-1"})

    render_schedule_page(st, PilotServiceAdapter(StubService()), reveal_workers=False)

    assert st.dataframes, "a tabela da programação deveria ter sido desenhada"
    assert not any("extra visual" in message for message in st.infos)
```

O dublê registra `plotly_chart` pelo `__getattr__` sem erro, então o teste falha hoje pela mensagem de instalação e passa quando o ramo morto sai.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/presentation/test_schedule_page.py -v`
Expected: FAIL — o `except ModuleNotFoundError` ainda está no código

- [ ] **Step 3: Write minimal implementation**

Em `src/presentation/pages.py`, dentro de `render_schedule_page`, substitua:

```python
    try:
        st.plotly_chart(_schedule_figure(filtered), use_container_width=True)
    except ModuleNotFoundError:
        st.info("Instale o extra visual do piloto para habilitar o cronograma Plotly.")
```

por:

```python
    st.plotly_chart(_schedule_figure(filtered), use_container_width=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/presentation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/presentation/pages.py tests/unit/presentation/test_schedule_page.py
git commit -m "fix: stop suggesting an install that cannot apply"
```

---

### Task 8: Seleção de operação por linha da tabela, não por lista de 1.200 itens

`render_ranking_page` oferece `st.selectbox("Detalhar operação", …)` com uma opção por operação — 1.200 no snapshot da Planta Modelo. O Streamlit 1.61 suporta seleção de linha na própria tabela.

**Files:**
- Modify: `src/presentation/pages.py` (`render_ranking_page`)
- Test: `tests/unit/presentation/test_ranking_selection.py` (criar)

**Interfaces:**
- Consumes: `FakeStreamlit` (Task 1).
- Produces: `selected_operation_id(selection: Any, rows: list[dict[str, Any]]) -> str | None` em `src/presentation/view_models.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/presentation/test_ranking_selection.py
from __future__ import annotations

from presentation.view_models import selected_operation_id

ROWS = [{"operação": "op-a"}, {"operação": "op-b"}, {"operação": "op-c"}]


def test_a_selected_row_resolves_to_its_operation() -> None:
    selection = {"selection": {"rows": [1]}}

    assert selected_operation_id(selection, ROWS) == "op-b"


def test_no_selection_resolves_to_nothing() -> None:
    assert selected_operation_id({"selection": {"rows": []}}, ROWS) is None


def test_an_out_of_range_row_is_ignored_instead_of_raising() -> None:
    assert selected_operation_id({"selection": {"rows": [99]}}, ROWS) is None


def test_a_payload_without_selection_is_tolerated() -> None:
    assert selected_operation_id(None, ROWS) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/presentation/test_ranking_selection.py -v`
Expected: FAIL com `ImportError: cannot import name 'selected_operation_id'`

- [ ] **Step 3: Write minimal implementation**

Em `src/presentation/view_models.py`:

```python
def selected_operation_id(selection: Any, rows: list[dict[str, Any]]) -> str | None:
    """Traduz a seleção de linha do Streamlit no identificador da operação."""

    payload = _mapping(selection).get("selection")
    if not isinstance(payload, Mapping):
        return None
    indexes = payload.get("rows")
    if not isinstance(indexes, (list, tuple)) or not indexes:
        return None
    index = indexes[0]
    if not isinstance(index, int) or not 0 <= index < len(rows):
        return None
    return str(rows[index].get("operação", "")) or None
```

Em `src/presentation/pages.py`, dentro de `render_ranking_page`, substitua o bloco `st.dataframe(...)` seguido do `st.selectbox("Detalhar operação", …)` por:

```python
    table = [{key: row.get(key) for key in visible_columns} for row in filtered]
    event = st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        height=520,
        on_select="rerun",
        selection_mode="single-row",
    )
    if not filtered:
        return
    st.caption("Selecione uma linha da tabela para ver as parcelas do score.")
    selected = selected_operation_id(event, filtered)
    if selected is None:
        return
```

Acrescente `selected_operation_id` ao import de `presentation.view_models` em `pages.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/presentation -v && uv run mypy src tests`
Expected: PASS e mypy limpo

- [ ] **Step 5: Commit**

```bash
git add src/presentation/view_models.py src/presentation/pages.py tests/unit/presentation/test_ranking_selection.py
git commit -m "feat: select an operation by table row instead of a 1200-item dropdown"
```

---

### Task 9: Hash da verificação ganha rótulo e propósito

`render_verification_page` imprime o hash de 64 caracteres em `st.code` sem rótulo. Quem lê não sabe o que é nem o que fazer com ele.

**Files:**
- Modify: `src/presentation/pages.py` (`render_verification_page`)
- Test: `tests/unit/presentation/test_verification_page.py` (criar)

**Interfaces:**
- Consumes: `FakeStreamlit` (Task 1).
- Produces: nada novo.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/presentation/test_verification_page.py
from __future__ import annotations

from typing import Any

from presentation.pages import render_verification_page
from presentation.service_adapter import PilotServiceAdapter
from tests.support.fake_streamlit import FakeStreamlit


class StubService:
    def get_run(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "completed"}

    def get_verification(self, run_id: str) -> dict[str, Any]:
        return {"valid": True, "input_hash": "a" * 64, "violations": []}

    def list_snapshots(self) -> list[Any]:
        return []

    def start_run(self, **kwargs: Any) -> dict[str, Any]:
        return {}

    def get_backlog(self, run_id: str) -> dict[str, Any]:
        return {}

    def get_schedule(self, run_id: str) -> dict[str, Any]:
        return {}

    def record_decision(self, **kwargs: Any) -> dict[str, Any]:
        return {}

    def record_feedback(self, **kwargs: Any) -> list[Any]:
        return []

    def export_run(self, **kwargs: Any) -> dict[str, Any]:
        return {}


def test_the_input_hash_is_explained_not_just_printed() -> None:
    st = FakeStreamlit({"active_run_id": "run-1"})

    render_verification_page(st, PilotServiceAdapter(StubService()))

    explained = " ".join(st.captions)
    assert "reprodu" in explained.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/presentation/test_verification_page.py -v`
Expected: FAIL — nenhuma legenda explica o hash

- [ ] **Step 3: Write minimal implementation**

Em `src/presentation/pages.py`, dentro de `render_verification_page`, substitua `st.code(str(verification["input_hash"]), language=None)` por:

```python
    st.caption(
        "Impressão digital da entrada verificada. Duas execuções sobre o mesmo "
        "snapshot e a mesma configuração produzem o mesmo valor; é assim que se "
        "comprova a reprodutibilidade da proposta."
    )
    st.code(str(verification["input_hash"]), language=None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/presentation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/presentation/pages.py tests/unit/presentation/test_verification_page.py
git commit -m "docs: explain what the verification hash is for"
```

---

### Task 10: Suíte completa e verificação final

**Files:**
- Nenhum arquivo novo.

**Interfaces:**
- Consumes: todas as tarefas anteriores.
- Produces: nada.

- [ ] **Step 1: Rodar a suíte inteira**

Run: `uv run pytest`
Expected: todos os testes passam; a contagem cresceu em relação aos 206 do início

- [ ] **Step 2: Lint e tipos**

Run: `uv run ruff check src tests && uv run mypy src tests`
Expected: `All checks passed!` e `Success: no issues found`

- [ ] **Step 3: Subir o piloto e conferir as correções na tela**

```bash
export MAIA_PILOT_PASSWORD='piloto-maia-local'
.venv/bin/maia-pcm-pilot
```

Confira, em ordem: os três contadores da tela inicial mostram números; a tela de configuração informa 1.200 operações no escopo; o período sugerido começa em 18/08/2026; abrir "Ranking explicável" sem run oferece o botão de atalho; a barra de progresso avança conforme as etapas; selecionar uma linha da tabela abre as parcelas do score.

- [ ] **Step 4: Commit final**

```bash
git commit --allow-empty -m "chore: close UX phase 1"
```

---

## Fora desta fase

As correções abaixo dependem da direção visual escolhida (A, B ou C) no canvas de design e serão planejadas depois da escolha:

- ordem e hierarquia da navegação de dez itens;
- ação primária na tela inicial e ponto de partida do fluxo;
- densidade da tela de configuração (13 campos numéricos sem faixa recomendada nem botão de restaurar padrões);
- composição da tela de programação, hoje empilhando Gantt e tabela de 469 linhas;
- multiselects de Ativo e Localização com cerca de 1.400 opções, cuja solução depende do layout adotado;
- o botão "Atualizar estado", que hoje obriga o usuário a fazer polling manual. `st.fragment(run_every=…)` resolveria, mas trocar polling manual por atualização automática muda o modelo de execução da tela, e com a execução medida em ~5 s vale decidir antes se ela continua assíncrona.
