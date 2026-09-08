"""Aplicação Streamlit multipágina do piloto MAIA/PCM."""

from __future__ import annotations

import importlib
import os
from typing import Any

from presentation.pages import (
    PAGE_LABELS,
    START_PAGE,
    inject_styles,
    render_context_strip,
    render_page,
)
from presentation.privacy import (
    anonymous_access_enabled,
    password_is_valid,
    raw_worker_ids_enabled,
)
from presentation.service_adapter import PilotServiceAdapter, load_pilot_service
from presentation.view_models import run_status_view, to_plain


def _streamlit() -> Any:
    try:
        return importlib.import_module("streamlit")
    except ModuleNotFoundError as error:
        raise SystemExit(
            "Streamlit não está instalado. Instale as dependências opcionais do piloto."
        ) from error


def _authenticate(st: Any) -> None:
    expected = os.environ.get("MAIA_PILOT_PASSWORD")
    anonymous = anonymous_access_enabled(os.environ)
    if not expected and not anonymous:
        st.error(
            "A interface está bloqueada: defina MAIA_PILOT_PASSWORD. "
            "Para um ambiente local descartável, o acesso sem senha exige "
            "MAIA_PILOT_ALLOW_ANONYMOUS=true explicitamente."
        )
        st.stop()
    if not expected:
        st.warning("Modo anônimo explicitamente habilitado para este ambiente.")
        return
    if st.session_state.get("pilot_authenticated") is True:
        return

    st.title("Acesso ao piloto MAIA")
    with st.form("pilot-auth"):
        supplied = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar", type="primary")
    if submitted:
        if password_is_valid(expected, supplied):
            st.session_state["pilot_authenticated"] = True
            st.rerun()
        else:
            st.error("Credencial inválida.")
    st.stop()


def _service(st: Any) -> PilotServiceAdapter:
    existing = st.session_state.get("pilot_service")
    if isinstance(existing, PilotServiceAdapter):
        return existing
    try:
        service = load_pilot_service()
    except Exception as error:
        st.error(
            "Não foi possível inicializar o serviço do piloto. Verifique os diretórios "
            "autorizados e o banco local; nenhum detalhe sensível foi exibido."
        )
        st.stop()
        raise RuntimeError("unreachable after streamlit stop") from error
    st.session_state["pilot_service"] = service
    return service


def _context_items(
    st: Any,
    service: Any,
    tenant_label: str,
) -> list[tuple[str, str, bool]]:
    """Monta a faixa: de quais dados se fala e o que o piloto não faz.

    A garantia de somente leitura vive aqui, uma vez, em vez de repetir um
    aviso em bloco nas dez telas.
    """

    items: list[tuple[str, str, bool]] = [("fábrica", tenant_label, False)]
    selected = st.session_state.get("selected_snapshot_id")
    if selected:
        try:
            for snapshot in service.list_snapshots():
                plain = to_plain(snapshot)
                if not isinstance(plain, dict):
                    continue
                if str(plain.get("snapshot_id", "")) == str(selected):
                    items.append(("corte dos dados", str(plain.get("as_of", ""))[:10], False))
                    break
        except Exception:
            pass
    items.append(("escrita na Tractian", "nenhuma", False))
    return items


def _select_page(label: str) -> None:
    """Muda de tela por callback.

    O callback roda no início da próxima execução, antes de qualquer widget
    reivindicar a chave, que é o único momento em que escrever em
    ``session_state`` é legal.
    """

    import streamlit as streamlit_module

    streamlit_module.session_state["pilot_page"] = label


def _render_run_card(st: Any, service: Any) -> None:
    """Cartela de estado: qual semana está aberta e o que ela contém."""

    identifier = st.session_state.get("active_run_id")
    if not identifier:
        st.markdown(
            '<div class="maia-estado">Nenhuma semana proposta ainda.</div>',
            unsafe_allow_html=True,
        )
        return
    try:
        run = service.get_run(str(identifier))
        status = run_status_view(run)["status"]
        plain = to_plain(run)
        summary = plain.get("summary") if isinstance(plain, dict) else None
    except Exception:
        st.markdown(
            '<div class="maia-estado">Não foi possível ler o estado da semana.</div>',
            unsafe_allow_html=True,
        )
        return

    linhas = [f'<div class="maia-linha"><span>estado</span><b>{status}</b></div>']
    if isinstance(summary, dict):
        linhas.append(
            '<div class="maia-linha"><span>alocadas</span>'
            f'<b>{summary.get("assignments", "—")}</b></div>'
        )
        linhas.append(
            '<div class="maia-linha"><span>fora</span>'
            f'<b>{summary.get("unscheduled", "—")}</b></div>'
        )
        violations = summary.get("violations")
        alerta = " class=\"maia-alerta\"" if violations else ""
        linhas.append(
            '<div class="maia-linha"><span>violações</span>'
            f"<b{alerta}>{violations if violations is not None else '—'}</b></div>"
        )
    st.markdown(
        f'<div class="maia-estado">{"".join(linhas)}</div>',
        unsafe_allow_html=True,
    )


def main() -> None:
    st = _streamlit()
    st.set_page_config(
        page_title="MAIA · Piloto PCM",
        page_icon="🛠️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_styles(st)
    _authenticate(st)
    service = _service(st)

    tenant_label = (
        os.environ.get("MAIA_PILOT_TENANT_LABEL", "Planta Modelo").strip() or "Planta Modelo"
    )
    reveal_workers = raw_worker_ids_enabled(os.environ)
    default_user = os.environ.get("MAIA_PILOT_USER", "avaliador-piloto")

    with st.sidebar:
        st.markdown(
            '<div class="maia-titulo" style="margin-bottom:.9rem">'
            '<h1 style="font-size:1.9rem">MAIA</h1></div>',
            unsafe_allow_html=True,
        )

        current = st.session_state.get("pilot_page") or START_PAGE
        for label in PAGE_LABELS:
            st.button(
                label,
                key=f"nav-{label}",
                use_container_width=True,
                type="primary" if label == current else "tertiary",
                on_click=_select_page,
                args=(label,),
            )
        page = current

        _render_run_card(st, service)

        st.divider()
        user_name = st.text_input("Quem está avaliando", value=default_user).strip()
        if not user_name:
            user_name = "avaliador-piloto"
        if reveal_workers:
            st.caption("Identificadores de origem visíveis por variável de ambiente.")
        else:
            st.caption("Executantes pseudonimizados.")

    render_context_strip(st, _context_items(st, service, tenant_label))
    render_page(
        page,
        st,
        service,
        st.session_state,
        tenant_label=tenant_label,
        reveal_workers=reveal_workers,
        user_name=user_name,
    )


if __name__ == "__main__":
    main()

