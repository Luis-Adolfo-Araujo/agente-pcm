from __future__ import annotations

from typing import Any

import pytest

from presentation import pages
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


def test_a_failing_chart_surfaces_instead_of_being_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O handler removido transformava um erro real numa instrução impossível."""

    def _explode(rows: list[dict[str, Any]]) -> Any:
        raise ModuleNotFoundError("plotly")

    monkeypatch.setattr(pages, "_schedule_figure", _explode)
    st = FakeStreamlit({"active_run_id": "run-1"})

    with pytest.raises(ModuleNotFoundError):
        render_schedule_page(st, PilotServiceAdapter(StubService()), reveal_workers=False)

    assert not any("extra visual" in message for message in st.infos)
