from __future__ import annotations

from datetime import date
from typing import Any

from presentation.pages import default_period, render_configuration_page
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

    escrito = " ".join(st.markdowns)
    assert "1200" in escrito or "1.200" in escrito
    assert "—" not in escrito


def test_default_period_starts_the_day_after_the_snapshot_cut() -> None:
    start, end = default_period(date(2026, 8, 17))

    assert start == date(2026, 8, 18)
    assert end == date(2026, 8, 24)


def test_default_period_covers_seven_full_days() -> None:
    start, end = default_period(date(2026, 1, 31))

    assert (end - start).days == 6
