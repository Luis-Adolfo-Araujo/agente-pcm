"""Páginas do piloto; o objeto Streamlit é recebido por injeção."""

from __future__ import annotations

import importlib
from collections import Counter
from collections.abc import MutableMapping, Sequence
from datetime import date, datetime, time, timedelta
from typing import Any

from domain.planning.config import (
    DurationConfig,
    ExecutantConfig,
    MaterialConfig,
    OptimizerConfig,
    PlanningConfig,
    RankingConfig,
)
from domain.planning.entities import PlanningRequest, TimeWindow
from presentation.privacy import pseudonymize_export, pseudonymize_worker_fields
from presentation.service_adapter import PilotServiceAdapter
from presentation.view_models import (
    READY_STATUSES,
    backlog_rows,
    capacity_rows,
    coverage_view,
    duration_rows,
    executant_rows,
    execution_progress,
    filter_backlog,
    material_rows,
    operation_detail,
    quality_rows,
    run_id,
    run_rows,
    run_status_view,
    schedule_rows,
    selected_operation_id,
    snapshot_rows,
    to_plain,
    trace_rows,
    unscheduled_rows,
    verification_view,
)

# Quatro telas, uma por etapa do ciclo semanal do PCM. Cada uma reúne o que
# antes eram telas separadas: a ordem continua carregando informação, mas o
# planejador para de precisar caçar em qual das dez ele está.
PAGE_LABELS = (
    "Preparar",
    "A semana",
    "Por quê",
    "Decidir",
)

START_PAGE = "Preparar"

_READY_STATUSES = READY_STATUSES
_RUNNING_STATUSES = frozenset({"queued", "pending", "running", "processing"})


def default_period(as_of_date: date) -> tuple[date, date]:
    """Primeira janela completa de sete dias após o corte dos dados.

    Ancorar no snapshot, e não no relógio, mantém a simulação perto dos dados
    mesmo quando o snapshot envelhece.
    """

    start = as_of_date + timedelta(days=1)
    return start, start + timedelta(days=6)


def inject_styles(st: Any) -> None:
    """Aplica o sistema visual do piloto.

    A referência é o quadro de programação: um painel pautado, de linhas por
    executante e colunas por dia, montado à mão na reunião de segunda. Daí vêm
    as réguas em lugar de cartões, o raio quase zero e a ausência de sombra. O
    verde é o da borda cortada do vidro float e fica reservado à fase corrente
    e à ação primária; o óxido marca atraso e bloqueio.
    """

    st.markdown(
        """
        <style>
          :root {
            --maia-vidro: #EDF1EF;
            --maia-papel: #FBFCFC;
            --maia-tinta: #10201D;
            --maia-borda: #0B6B58;
            --maia-oxido: #A4442A;
            --maia-cinza: #5E706B;
            --maia-regua: #CBD6D2;
          }

          /* Réguas, não cartões: sem sombra e sem canto redondo em lugar nenhum. */
          div[data-testid="stDataFrame"],
          div[data-testid="stMetric"],
          div[data-testid="stExpander"] {
            box-shadow: none;
          }
          div[data-testid="stMetric"] {
            border: 0;
            border-top: 2px solid var(--maia-tinta);
            padding: .55rem .1rem 0;
            background: transparent;
          }
          div[data-testid="stMetricLabel"] p {
            font-family: "Plex Mono", ui-monospace, monospace;
            font-size: .68rem;
            letter-spacing: .1em;
            text-transform: uppercase;
            color: var(--maia-cinza);
          }
          div[data-testid="stMetricValue"] {
            font-family: "Archivo Condensed", "Plex Sans", sans-serif;
            font-weight: 600;
            letter-spacing: -.01em;
          }

          /* Cabeçalho da tela: tipografia de placa, não de dashboard. */
          .maia-titulo {
            border-bottom: 2px solid var(--maia-tinta);
            padding-bottom: .5rem;
            margin-bottom: .2rem;
          }
          .maia-titulo h1 {
            font-family: "Archivo Condensed", sans-serif;
            font-weight: 600;
            font-size: 2.6rem;
            line-height: 1.02;
            letter-spacing: -.01em;
            color: var(--maia-tinta);
            margin: 0;
          }

          /* A faixa de estado: sempre diz de quais dados e de que semana se fala. */
          .maia-faixa {
            display: flex;
            flex-wrap: wrap;
            gap: 0 2.2rem;
            padding: .5rem 0 .7rem;
            border-bottom: 1px solid var(--maia-regua);
            margin-bottom: 1.4rem;
            font-family: "Plex Mono", ui-monospace, monospace;
            font-size: .72rem;
            letter-spacing: .06em;
            text-transform: uppercase;
            color: var(--maia-cinza);
          }
          .maia-faixa b {
            color: var(--maia-tinta);
            font-weight: 500;
          }
          .maia-faixa .maia-alerta {
            color: var(--maia-oxido);
          }

          /* Rótulo de fase na barra lateral. */
          .maia-fase {
            font-family: "Plex Mono", ui-monospace, monospace;
            font-size: .64rem;
            letter-spacing: .16em;
            text-transform: uppercase;
            color: var(--maia-cinza);
            border-top: 1px solid var(--maia-regua);
            padding-top: .55rem;
            margin: 1rem 0 .1rem;
          }

          /* Navegação: alinhada à esquerda, régua fina, sem cara de botão. */
          section[data-testid="stSidebar"] div[data-testid="stButton"] button {
            justify-content: flex-start;
            text-align: left;
            border: 0;
            padding: .2rem .1rem;
            font-size: .93rem;
            min-height: 0;
          }
          section[data-testid="stSidebar"] div[data-testid="stButton"] button p {
            font-weight: 400;
          }
          section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] {
            background: transparent;
            color: var(--maia-borda);
          }
          section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] p {
            font-weight: 600;
          }

          /* Cartela de estado do run, ao pé da barra lateral. */
          .maia-estado {
            border-top: 2px solid var(--maia-tinta);
            padding-top: .5rem;
            margin-top: 1.4rem;
            font-family: "Plex Mono", ui-monospace, monospace;
            font-size: .72rem;
            color: var(--maia-cinza);
            line-height: 1.7;
          }
          .maia-estado .maia-linha {
            display: flex;
            justify-content: space-between;
            gap: .8rem;
          }
          .maia-estado b {
            color: var(--maia-tinta);
            font-weight: 500;
          }

          /* Números que são código continuam com cara de código. */
          .maia-dado {
            font-family: "Plex Mono", ui-monospace, monospace;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_title(st: Any, title: str) -> None:
    """Desenha o título da tela com o tratamento tipográfico do piloto."""

    st.markdown(
        f'<div class="maia-titulo"><h1>{title}</h1></div>',
        unsafe_allow_html=True,
    )


def render_context_strip(st: Any, items: Sequence[tuple[str, str, bool]]) -> None:
    """Desenha a faixa de estado: rótulo, valor e se o valor pede atenção."""

    if not items:
        return
    parts = [
        f'<span>{label} <b class="{"maia-alerta" if alert else ""}">{value}</b></span>'
        for label, value, alert in items
    ]
    st.markdown(
        f'<div class="maia-faixa">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def _safe_error(st: Any, action: str) -> None:
    st.error(
        f"Não foi possível {action}. A operação falhou de forma segura e nenhuma "
        "alteração foi feita na origem."
    )


def _go_to(page: str) -> None:
    """Muda de tela por callback, o único momento em que a escrita é legal."""

    import streamlit as streamlit_module

    streamlit_module.session_state["pilot_page"] = page


def _active_run(st: Any) -> str | None:
    identifier = st.session_state.get("active_run_id")
    if not identifier:
        st.info(
            "Esta tela lê uma semana já proposta, e ainda não existe nenhuma. "
            "Monte a primeira para começar."
        )
        # Use on_click callback instead of writing st.session_state during render.
        # Streamlit forbids modifying a widget's session_state key during the render
        # that instantiated the widget (raises StreamlitAPIException). Callbacks run at
        # the START of the next script run, before any widgets are instantiated, so the
        # assignment is legal there. The callback implicitly triggers a rerun.
        def _go_to_configuration() -> None:
            st.session_state["pilot_page"] = START_PAGE

        st.button(
            "Montar a semana",
            type="primary",
            on_click=_go_to_configuration,
        )
        return None
    return str(identifier)


def _selected_snapshot(st: Any, service: PilotServiceAdapter) -> Any | None:
    selected = st.session_state.get("selected_snapshot_id")
    if not selected:
        return None
    for snapshot in service.list_snapshots():
        plain = to_plain(snapshot)
        if isinstance(plain, dict) and str(
            plain.get("snapshot_id", plain.get("id", ""))
        ) == str(selected):
            return snapshot
    return None


def _parse_aware(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else None
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _run_is_ready(st: Any, service: PilotServiceAdapter, identifier: str) -> bool:
    try:
        status = run_status_view(service.get_run(identifier))["status"]
    except Exception:
        _safe_error(st, "consultar o estado da simulação")
        return False
    if status in _READY_STATUSES:
        return True
    if status in _RUNNING_STATUSES:
        st.info("A simulação ainda está em processamento. Consulte a tela Execução.")
    else:
        st.warning("A simulação não possui artefatos prontos para consulta.")
    return False


def render_snapshot_page(
    st: Any,
    service: PilotServiceAdapter,
    *,
    tenant_label: str,
) -> None:
    st.subheader("Os dados")
    try:
        snapshots = tuple(service.list_snapshots())
    except Exception:
        _safe_error(st, "listar os snapshots autorizados")
        return
    if not snapshots:
        st.info(
            "Nenhum recorte de dados foi encontrado. Um administrador precisa "
            "publicar um arquivo no diretório autorizado antes do primeiro uso."
        )
        return

    rows = snapshot_rows(snapshots)
    identifiers = [str(row["snapshot_id"]) for row in rows]
    current = st.session_state.get("selected_snapshot_id")
    index = identifiers.index(current) if current in identifiers else 0

    st.markdown(
        "O MAIA propõe uma semana de manutenção a partir de um recorte "
        "congelado dos dados da Tractian. Ele nunca escreve na origem: "
        "aprovar aqui não publica programação nem altera OS."
    )

    selected = st.selectbox(
        "Recorte em uso",
        identifiers,
        index=index,
        format_func=lambda identifier: f"{tenant_label} · corte {identifier[-29:-19]}",
    )
    st.session_state["selected_snapshot_id"] = selected
    selected_index = identifiers.index(selected)
    selected_snapshot = snapshots[selected_index]
    selected_row = rows[selected_index]

    columns = st.columns(4)
    columns[0].metric("Operações no backlog", selected_row["operações"])
    columns[1].metric("Pessoas", selected_row["pessoas"])
    columns[2].metric("Itens de estoque", selected_row["materiais"])
    columns[3].metric("Corte dos dados", str(selected_row["data_corte"])[:10])

    st.button(
        "Montar a semana",
        type="primary",
        on_click=_go_to,
        args=(START_PAGE,),
    )

    st.divider()
    st.subheader("O que pode enfraquecer a recomendação")
    st.markdown(
        "Campo em branco não vira valor baixo: o agente marca a ausência e "
        "segue. Os números abaixo dizem em quanto do backlog cada informação "
        "existe de fato."
    )
    quality = quality_rows(selected_snapshot)
    if quality:
        st.dataframe(quality, use_container_width=True, hide_index=True, height=320)
    else:
        st.info(
            "Este recorte não publicou indicadores de qualidade. A interface não "
            "recalcula cobertura para não criar uma segunda fonte de verdade."
        )

    with st.expander("Limitações deste recorte"):
        plain = to_plain(selected_snapshot)
        technical_tenant = plain.get("tenant_id", "—") if isinstance(plain, dict) else "—"
        st.markdown(
            "- Os dados são um recorte histórico, não uma conexão em tempo real.\n"
            "- Criticidade e tipo de atividade têm cobertura baixa.\n"
            "- Ordem sem material cadastrado fica com prontidão desconhecida, "
            "nunca com prontidão confirmada.\n"
            "- Histórico de execução é evidência de experiência, não certificação.\n"
            f"- Tenant técnico: `{technical_tenant}`"
        )


def _configuration_form(st: Any, *, as_of_date: date) -> tuple[date, date, PlanningConfig, bool]:
    """Pergunta o mínimo: a semana. O resto tem padrão e fica recolhido."""

    defaults = PlanningConfig()
    suggested_start, suggested_end = default_period(as_of_date)

    columns = st.columns(2)
    period_start = columns[0].date_input("Primeiro dia", value=suggested_start)
    period_end = columns[1].date_input("Último dia", value=suggested_end)

    with st.expander("Ajustar os critérios (opcional)"):
        st.caption(
            "Os padrões abaixo são os que o PCM aprovou. Mexa só se quiser "
            "testar uma hipótese; cada execução guarda os valores usados."
        )

        st.markdown("**Como a fila é ordenada**")
        st.caption(
            "Peso de cada fator no score de prioridade. Somados não precisam "
            "dar 1: o que importa é a proporção entre eles."
        )
        weight_columns = st.columns(4)
        priority_weight = weight_columns[0].number_input(
            "Prioridade da OS", min_value=0.0, value=defaults.ranking.priority_weight, step=0.05
        )
        age_weight = weight_columns[1].number_input(
            "Dias em aberto", min_value=0.0, value=defaults.ranking.age_weight, step=0.05
        )
        sla_weight = weight_columns[2].number_input(
            "Prazo (SLA)", min_value=0.0, value=defaults.ranking.sla_weight, step=0.05
        )
        criticality_weight = weight_columns[3].number_input(
            "Criticidade do ativo",
            min_value=0.0,
            value=defaults.ranking.criticality_weight,
            step=0.05,
        )

        rule_columns = st.columns(3)
        sla_horizon = rule_columns[0].number_input(
            "Prazo deixa de urgir após (dias)",
            min_value=1,
            value=defaults.ranking.sla_horizon_days,
        )
        age_cap = rule_columns[1].number_input(
            "Idade satura em (dias)", min_value=1, value=defaults.ranking.age_cap_days
        )
        overdue_cap = rule_columns[2].number_input(
            "Atraso satura em (dias)", min_value=1, value=defaults.ranking.overdue_cap_days
        )

        st.markdown("**Quando falta informação**")
        skill_columns = st.columns(4)
        default_duration = skill_columns[0].number_input(
            "Duração assumida sem histórico (min)",
            min_value=1,
            value=defaults.duration.default_minutes or 60,
        )
        minimum_sample = skill_columns[1].number_input(
            "Execuções mínimas para confiar no histórico",
            min_value=1,
            value=defaults.duration.minimum_sample_size,
        )
        top_n = skill_columns[2].number_input(
            "Executantes sugeridos por OS",
            min_value=1,
            max_value=50,
            value=defaults.executants.top_n,
        )
        granularity = skill_columns[3].number_input(
            "Encaixe do horário (min)",
            min_value=1,
            value=defaults.optimizer.slot_granularity_minutes,
        )
        allow_partial = st.checkbox(
            "Programar mesmo com material só parcialmente disponível",
            value=defaults.materials.allow_partial,
        )
        consider_inbound = st.checkbox(
            "Contar material com entrada prevista dentro do período",
            value=defaults.materials.consider_expected_inbound,
        )

    config = PlanningConfig(
        ranking=RankingConfig(
            priority_scores=defaults.ranking.priority_scores,
            priority_weight=priority_weight,
            age_weight=age_weight,
            sla_weight=sla_weight,
            criticality_weight=criticality_weight,
            age_cap_days=int(age_cap),
            sla_horizon_days=int(sla_horizon),
            overdue_cap_days=int(overdue_cap),
        ),
        duration=DurationConfig(
            prefer_planned=defaults.duration.prefer_planned,
            minimum_sample_size=int(minimum_sample),
            maximum_valid_minutes=defaults.duration.maximum_valid_minutes,
            default_minutes=int(default_duration),
            title_similarity_threshold=defaults.duration.title_similarity_threshold,
        ),
        materials=MaterialConfig(
            consider_expected_inbound=consider_inbound,
            allow_partial=allow_partial,
        ),
        executants=ExecutantConfig(
            top_n=int(top_n),
            team_weight=defaults.executants.team_weight,
            asset_weight=defaults.executants.asset_weight,
            activity_weight=defaults.executants.activity_weight,
            location_weight=defaults.executants.location_weight,
            frequency_weight=defaults.executants.frequency_weight,
        ),
        optimizer=OptimizerConfig(
            algorithm_version=defaults.optimizer.algorithm_version,
            slot_granularity_minutes=int(granularity),
        ),
    )
    submitted = st.form_submit_button("Montar a semana", type="primary")
    return period_start, period_end, config, submitted


def render_configuration_page(st: Any, service: PilotServiceAdapter) -> None:
    st.subheader("A semana a programar")
    snapshot = _selected_snapshot(st, service)
    if snapshot is None:
        st.info(
            "Escolha primeiro o recorte de dados. Ele define quais ordens "
            "entram na conta."
        )
        st.button("Escolher o recorte", on_click=_go_to, args=(START_PAGE,))
        return
    plain_snapshot = to_plain(snapshot)
    if not isinstance(plain_snapshot, dict):
        st.error(
            "O recorte selecionado não tem o formato esperado. Escolha outro em "
            "Dados congelados."
        )
        return
    snapshot_identifier = str(
        plain_snapshot.get("snapshot_id", plain_snapshot.get("id", ""))
    )
    as_of = _parse_aware(plain_snapshot.get("as_of"))
    tenant_id = str(plain_snapshot.get("tenant_id", ""))
    if as_of is None or not tenant_id:
        st.error(
            "O recorte não informa fábrica e data de corte com fuso horário. "
            "Peça ao administrador um recorte válido."
        )
        return

    counts = snapshot_rows([plain_snapshot])[0]
    st.markdown(
        f"Escolha a semana. O agente vai olhar as **{counts['operações']} operações** "
        "do backlog e propor quem faz o quê, em que dia."
    )

    with st.form("planning-config"):
        period_start, period_end, config, submitted = _configuration_form(
            st, as_of_date=as_of.date()
        )
    if not submitted:
        return
    if period_end < period_start:
        st.error("O último dia precisa ser igual ou posterior ao primeiro.")
        return

    start = datetime.combine(period_start, time.min, tzinfo=as_of.tzinfo)
    end = datetime.combine(period_end + timedelta(days=1), time.min, tzinfo=as_of.tzinfo)
    request = PlanningRequest(
        tenant_id=tenant_id,
        period=TimeWindow(start=start, end=end),
        as_of=as_of,
        dry_run=True,
    )
    try:
        with st.spinner("Montando a semana…"):
            run = service.start_run(
                snapshot_id=snapshot_identifier,
                request=request,
                config=config,
            )
    except Exception:
        _safe_error(st, "montar a semana")
        return
    identifier = run_id(run)
    if identifier is None:
        st.error("O serviço não devolveu um identificador de execução.")
        return
    st.session_state["active_run_id"] = identifier
    known = list(st.session_state.get("known_run_ids", []))
    if identifier not in known:
        known.append(identifier)
    st.session_state["known_run_ids"] = known
    # Levar o usuário ao andamento em vez de mandá-lo procurar a tela.
    st.session_state["pilot_page"] = "A semana"
    st.rerun()


def render_execution_page(st: Any, service: PilotServiceAdapter) -> None:
    identifier = _active_run(st)
    if identifier is None:
        return
    if st.button("Atualizar estado", type="primary"):
        pass  # O clique já provoca um novo ciclo do Streamlit.
    try:
        run = service.get_run(identifier)
    except Exception:
        _safe_error(st, "consultar a execução")
        return
    status = run_status_view(run)
    status_name = str(status["status"])
    st.metric("Estado", status_name.upper())
    st.progress(execution_progress(run))

    traces = trace_rows(run)
    if traces:
        st.subheader("Etapas concluídas")
        st.dataframe(traces, use_container_width=True, hide_index=True)
    elif status_name in _RUNNING_STATUSES:
        st.info("Aguardando o primeiro checkpoint da execução.")

    if status_name in _READY_STATUSES:
        st.success("Proposta pronta. As telas analíticas já podem ser consultadas.")
    elif status_name == "failed":
        st.error(
            "A simulação terminou em falha segura. Consulte o administrador pelo ID do run; "
            "nenhum dado da origem foi alterado."
        )
    else:
        st.caption(
            "Use Atualizar estado após alguns segundos. "
            "O processamento continua no serviço."
        )


def _completed_backlog(
    st: Any, service: PilotServiceAdapter
) -> tuple[str, Any] | tuple[None, None]:
    identifier = _active_run(st)
    if identifier is None or not _run_is_ready(st, service, identifier):
        return None, None
    try:
        return identifier, service.get_backlog(identifier)
    except Exception:
        _safe_error(st, "carregar os enriquecimentos do run")
        return None, None


def render_ranking_page(
    st: Any,
    service: PilotServiceAdapter,
    *,
    reveal_workers: bool,
) -> None:
    identifier, payload = _completed_backlog(st, service)
    if identifier is None:
        return
    rows = backlog_rows(payload)
    try:
        scheduled_ids = {
            str(row["operação"])
            for row in schedule_rows(service.get_schedule(identifier), payload)
        }
        for row in rows:
            row["programada"] = str(row["operação"]) in scheduled_ids
    except Exception:
        scheduled_ids = set()

    with st.expander("Filtros", expanded=True):
        filter_columns = st.columns(4)
        overdue = filter_columns[0].checkbox("Somente vencidas")
        priority_options = sorted({str(row["prioridade"]) for row in rows})
        priorities = set(filter_columns[1].multiselect("Prioridade", priority_options))
        material_options = sorted({str(row["material"]) for row in rows})
        materials = set(filter_columns[2].multiselect("Material", material_options))
        schedule_filter = filter_columns[3].selectbox(
            "Programação", ("Todas", "Programadas", "Não programadas")
        )
        second_row = st.columns(2)
        locations = set(
            second_row[0].multiselect(
                "Localização",
                sorted({str(row["localização"]) for row in rows}),
            )
        )
        assets = set(
            second_row[1].multiselect(
                "Ativo",
                sorted({str(row["ativo"]) for row in rows}),
            )
        )
    scheduled = {"Todas": None, "Programadas": True, "Não programadas": False}[
        schedule_filter
    ]
    filtered = filter_backlog(
        rows,
        overdue_only=overdue,
        priorities=priorities,
        locations=locations,
        assets=assets,
        material_statuses=materials,
        scheduled=scheduled,
    )
    st.caption(f"{len(filtered)} de {len(rows)} operações visíveis.")
    visible_columns = [
        "posição",
        "os",
        "operação",
        "título",
        "prioridade",
        "idade_dias",
        "sla",
        "criticidade",
        "score",
        "modelo",
        "prontidão",
        "programabilidade",
        "programada",
    ]
    table = [{key: row.get(key) for key in visible_columns} for row in filtered]
    event = st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        height=520,
        on_select="rerun",
        selection_mode="single-row",
        key="ranking-table",
    )
    if not filtered:
        return
    st.caption("Selecione uma linha da tabela para ver as parcelas do score.")
    selected = selected_operation_id(event, filtered)
    if selected is None:
        return
    detail = operation_detail(payload, selected)
    priority = detail.get("priority", {}) if isinstance(detail, dict) else {}
    if isinstance(priority, dict):
        st.subheader("Parcelas do score")
        st.dataframe(priority.get("components", []), use_container_width=True, hide_index=True)
        st.caption("Códigos: " + ", ".join(str(code) for code in priority.get("reason_codes", [])))
    with st.expander("Estado enriquecido completo"):
        st.json(pseudonymize_worker_fields(detail, reveal=reveal_workers))


def render_laboratory_page(
    st: Any,
    service: PilotServiceAdapter,
    *,
    reveal_workers: bool,
) -> None:
    _, payload = _completed_backlog(st, service)
    if payload is None:
        return
    duration_tab, material_tab, capacity_tab, executant_tab = st.tabs(
        ("Duração", "Materiais", "Capacidade", "Executantes")
    )
    with duration_tab:
        st.dataframe(duration_rows(payload), use_container_width=True, hide_index=True, height=520)
        st.caption("Divergência compara a duração adotada com a planejada, quando ambas existem.")
    with material_tab:
        st.dataframe(material_rows(payload), use_container_width=True, hide_index=True, height=520)
        st.caption("Entrada futura sem quantidade conhecida permanece bloqueadora.")
    with capacity_tab:
        capacities = capacity_rows(payload, reveal_workers=reveal_workers)
        st.dataframe(capacities, use_container_width=True, hide_index=True, height=520)
        if capacities:
            gross = sum(float(row["HH_bruto"]) for row in capacities)
            net = sum(float(row["HH_líquido"]) for row in capacities)
            first, second = st.columns(2)
            first.metric("HH bruto", f"{gross:.1f}")
            second.metric("HH líquido", f"{net:.1f}")
    with executant_tab:
        st.warning("Experiência histórica não comprova certificação profissional.")
        st.dataframe(
            executant_rows(payload, reveal_workers=reveal_workers),
            use_container_width=True,
            hide_index=True,
            height=520,
        )


def _schedule_figure(rows: list[dict[str, Any]]) -> Any:
    graph_objects = importlib.import_module("plotly.graph_objects")
    figure = graph_objects.Figure()
    for row in rows:
        start = _parse_aware(row.get("início"))
        end = _parse_aware(row.get("fim"))
        if start is None or end is None:
            continue
        score = float(row.get("prioridade_score", 0))
        color = "#A94442" if score >= 80 else "#D07A24" if score >= 60 else "#2F7D6D"
        figure.add_trace(
            graph_objects.Bar(
                x=[(end - start).total_seconds() * 1000],
                y=[row.get("executantes", "")],
                base=[start],
                orientation="h",
                marker_color=color,
                name=str(row.get("operação", "")),
                text=[f"{row.get('operação')} · {row.get('duração_min')} min"],
                hovertemplate="%{text}<extra></extra>",
            )
        )
    figure.update_layout(
        barmode="overlay",
        height=max(420, 42 * len({str(row.get("executantes")) for row in rows})),
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
        showlegend=False,
        xaxis={"title": "Data e horário", "type": "date"},
        yaxis={"title": "Executante"},
    )
    return figure


def render_schedule_page(
    st: Any,
    service: PilotServiceAdapter,
    *,
    reveal_workers: bool,
) -> None:
    identifier, backlog = _completed_backlog(st, service)
    if identifier is None:
        return
    try:
        schedule = service.get_schedule(identifier)
    except Exception:
        _safe_error(st, "carregar a programação")
        return
    rows = schedule_rows(schedule, backlog, reveal_workers=reveal_workers)
    if not rows:
        st.warning("O run não possui alocações.")
        return

    columns = st.columns(4)
    selected_team = columns[0].multiselect(
        "Equipe", sorted({str(row["equipe"]) for row in rows})
    )
    selected_location = columns[1].multiselect(
        "Localização", sorted({str(row["localização"]) for row in rows})
    )
    selected_asset = columns[2].multiselect(
        "Ativo", sorted({str(row["ativo"]) for row in rows})
    )
    selected_day = columns[3].multiselect(
        "Dia", sorted({str(row["início"])[:10] for row in rows})
    )
    filtered = [
        row
        for row in rows
        if (not selected_team or row["equipe"] in selected_team)
        and (not selected_location or row["localização"] in selected_location)
        and (not selected_asset or row["ativo"] in selected_asset)
        and (not selected_day or str(row["início"])[:10] in selected_day)
    ]
    st.plotly_chart(_schedule_figure(filtered), use_container_width=True)
    st.dataframe(filtered, use_container_width=True, hide_index=True, height=520)
    st.caption(
        "Visualização somente leitura. PRIORITY_ORDER, EXECUTANT_SCORE e "
        "EARLIEST_FEASIBLE_SLOT são regras fixas do baseline guloso."
    )


def render_unscheduled_page(st: Any, service: PilotServiceAdapter) -> None:
    identifier, backlog = _completed_backlog(st, service)
    if identifier is None:
        return
    try:
        schedule = service.get_schedule(identifier)
    except Exception:
        _safe_error(st, "carregar os bloqueios")
        return
    rows = unscheduled_rows(schedule, backlog)
    counts = Counter(str(row["motivo"]) for row in rows)
    coverage = coverage_view(schedule)
    first, second, third = st.columns(3)
    first.metric("Cobertura de capacidade", f"{coverage['cobertura_percent']:.1f}%")
    second.metric("Demanda do backlog", f"{coverage['demanda_hh']:.0f} HH")
    third.metric("Capacidade líquida", f"{coverage['disponível_hh']:.0f} HH")
    st.info(coverage["leitura"])
    st.caption(
        "Uma operação prioritária bloqueada continua visível; ela não perde prioridade "
        "por não ser programável."
    )
    if counts:
        st.dataframe(
            [{"motivo": reason, "quantidade": count} for reason, count in counts.most_common()],
            use_container_width=True,
            hide_index=True,
        )
    selected_reason = st.selectbox("Categoria", ("Todas", *sorted(counts)))
    filtered = rows if selected_reason == "Todas" else [
        row for row in rows if row["motivo"] == selected_reason
    ]
    st.dataframe(filtered, use_container_width=True, hide_index=True, height=560)


def render_verification_page(st: Any, service: PilotServiceAdapter) -> None:
    identifier = _active_run(st)
    if identifier is None or not _run_is_ready(st, service, identifier):
        return
    try:
        verification = verification_view(service.get_verification(identifier))
    except Exception:
        _safe_error(st, "carregar o relatório de verificação")
        return
    if verification["valid"]:
        st.success("Proposta tecnicamente válida: nenhuma violação dura encontrada.")
    else:
        st.error(
            f"Proposta inválida: {verification['error_count']} violação(ões) de erro. "
            "A aprovação está bloqueada."
        )
    st.caption(
        "Impressão digital da entrada verificada. Duas execuções sobre o mesmo "
        "snapshot e a mesma configuração produzem o mesmo valor; é assim que se "
        "comprova a reprodutibilidade da proposta."
    )
    st.code(str(verification["input_hash"]), language=None)
    st.dataframe(
        verification["violations"],
        use_container_width=True,
        hide_index=True,
        height=520,
    )


def render_decision_page(
    st: Any,
    service: PilotServiceAdapter,
    *,
    user_name: str,
) -> None:
    identifier, backlog = _completed_backlog(st, service)
    if identifier is None:
        return
    try:
        verification = verification_view(service.get_verification(identifier))
    except Exception:
        _safe_error(st, "validar a proposta antes da decisão")
        return

    st.subheader("Decisão sobre o dry-run")
    decision = st.radio("Decisão", ("Aprovar dry-run", "Rejeitar"), horizontal=True)
    reason = st.text_area("Motivo da decisão (obrigatório)", max_chars=1000)
    approve_selected = decision == "Aprovar dry-run"
    if approve_selected and not verification["valid"]:
        st.error("Aprovação desabilitada porque a proposta possui violação de erro.")
    if st.button(
        "Registrar decisão",
        type="primary",
        disabled=approve_selected and not verification["valid"],
    ):
        if not reason.strip():
            st.error("Informe o motivo antes de registrar a decisão.")
        else:
            try:
                service.record_decision(
                    run_id=identifier,
                    decision="approved" if approve_selected else "rejected",
                    decided_by=user_name,
                    reason=reason.strip(),
                )
                st.success("Decisão registrada. Nenhuma publicação foi feita na origem.")
            except Exception:
                _safe_error(st, "registrar a decisão")

    st.divider()
    st.subheader("Feedback para o golden set")
    operations = [str(row["operação"]) for row in backlog_rows(backlog)]
    if not operations:
        st.info("Não há operações para avaliar.")
        return
    feedback_operation = st.selectbox("Operação avaliada", operations)
    skill = st.selectbox(
        "Recomendação",
        ("ranking", "duration", "materials", "executants", "schedule"),
    )
    verdict = st.selectbox("Veredito", ("correct", "acceptable", "incorrect"))
    feedback_reason = st.text_area("Comentário do feedback", max_chars=1000)
    if st.button("Registrar feedback"):
        if not feedback_reason.strip():
            st.error("Informe um comentário para tornar o feedback auditável.")
        else:
            try:
                service.record_feedback(
                    run_id=identifier,
                    items=(
                        {
                            "operation_id": feedback_operation,
                            "skill": skill,
                            "verdict": verdict,
                            "reason": feedback_reason.strip(),
                        },
                    ),
                    recorded_by=user_name,
                )
                st.success("Feedback registrado para avaliação offline; ele não altera o modelo.")
            except Exception:
                _safe_error(st, "registrar o feedback")


def _session_runs(st: Any, service: PilotServiceAdapter) -> list[Any]:
    try:
        persisted = list(service.list_runs())
    except Exception:
        persisted = []
    known_ids = [str(identifier) for identifier in st.session_state.get("known_run_ids", [])]
    persisted_ids = {run_id(run) for run in persisted}
    for identifier in known_ids:
        if identifier in persisted_ids:
            continue
        try:
            persisted.append(service.get_run(identifier))
        except Exception:
            continue
    return persisted


def render_history_page(
    st: Any,
    service: PilotServiceAdapter,
    *,
    reveal_workers: bool,
) -> None:
    render_title(st, "Histórico e downloads")
    runs = _session_runs(st, service)
    rows = run_rows(runs)
    if not rows:
        st.info("Nenhuma simulação persistida foi encontrada.")
        return
    st.dataframe(rows, use_container_width=True, hide_index=True, height=360)
    identifiers = [str(row["run_id"]) for row in rows if row["run_id"]]
    selected = st.selectbox("Run", identifiers)
    if st.button("Usar este run nas telas"):
        st.session_state["active_run_id"] = selected
        st.success(f"Run ativo alterado para `{selected}`.")

    export_format = st.radio("Formato", ("json", "csv"), horizontal=True)
    if st.button("Preparar downloads"):
        try:
            files = service.export_files(run_id=selected, export_format=export_format)
        except Exception:
            _safe_error(st, "preparar os downloads")
            return
        safe_files: dict[str, bytes] = {}
        try:
            for filename, content in files.items():
                safe_files[filename] = pseudonymize_export(
                    content,
                    filename,
                    reveal=reveal_workers,
                )
        except (UnicodeDecodeError, ValueError):
            st.error(
                "O arquivo não pôde ser pseudonimizado com segurança e, por isso, "
                "o download foi bloqueado."
            )
            return
        st.session_state["prepared_downloads"] = safe_files

    for filename, content in st.session_state.get("prepared_downloads", {}).items():
        mime = "application/json" if filename.endswith(".json") else "text/csv"
        st.download_button(
            f"Baixar {filename}",
            data=content,
            file_name=filename,
            mime=mime,
        )


def render_prepare_page(
    st: Any,
    service: PilotServiceAdapter,
    *,
    tenant_label: str,
) -> None:
    """Escolher os dados e a semana, e disparar — em um lugar só."""

    render_title(st, "Preparar")
    render_snapshot_page(st, service, tenant_label=tenant_label)
    st.divider()
    render_configuration_page(st, service)


def render_week_page(
    st: Any,
    service: PilotServiceAdapter,
    *,
    reveal_workers: bool,
) -> None:
    """O resultado: o que entrou na semana e o que ficou de fora."""

    render_title(st, "A semana")
    identifier = _active_run(st)
    if identifier is None:
        return
    if not _run_is_ready(st, service, identifier):
        render_execution_page(st, service)
        return
    programada, fora = st.tabs(("Programação", "Fora da semana"))
    with programada:
        render_schedule_page(st, service, reveal_workers=reveal_workers)
    with fora:
        render_unscheduled_page(st, service)


def render_why_page(
    st: Any,
    service: PilotServiceAdapter,
    *,
    reveal_workers: bool,
) -> None:
    """Por que cada ordem está onde está, e se a proposta se sustenta."""

    render_title(st, "Por quê")
    fila, calculo, conferencia = st.tabs(
        ("Fila de prioridade", "Como o agente calculou", "Conferência")
    )
    with fila:
        render_ranking_page(st, service, reveal_workers=reveal_workers)
    with calculo:
        render_laboratory_page(st, service, reveal_workers=reveal_workers)
    with conferencia:
        render_verification_page(st, service)


def render_decide_page(
    st: Any,
    service: PilotServiceAdapter,
    *,
    reveal_workers: bool,
    user_name: str,
) -> None:
    """Aprovar ou rejeitar, e rever o que já foi decidido."""

    render_title(st, "Decidir")
    decisao, anteriores = st.tabs(("Decisão", "Execuções anteriores"))
    with decisao:
        render_decision_page(st, service, user_name=user_name)
    with anteriores:
        render_history_page(st, service, reveal_workers=reveal_workers)


def render_page(
    page: str,
    st: Any,
    service: PilotServiceAdapter,
    state: MutableMapping[str, Any],
    *,
    tenant_label: str,
    reveal_workers: bool,
    user_name: str,
) -> None:
    del state  # O Streamlit já expõe o mesmo mapping em session_state.
    if page == "Preparar":
        render_prepare_page(st, service, tenant_label=tenant_label)
    elif page == "A semana":
        render_week_page(st, service, reveal_workers=reveal_workers)
    elif page == "Por quê":
        render_why_page(st, service, reveal_workers=reveal_workers)
    else:
        render_decide_page(
            st,
            service,
            reveal_workers=reveal_workers,
            user_name=user_name,
        )


__all__ = [
    "PAGE_LABELS",
    "START_PAGE",
    "inject_styles",
    "render_context_strip",
    "render_page",
    "render_title",
]
