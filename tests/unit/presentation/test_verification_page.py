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
