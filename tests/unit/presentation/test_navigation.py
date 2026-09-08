from __future__ import annotations

from presentation.pages import _active_run
from tests.support.fake_streamlit import FakeStreamlit


def test_a_screen_without_a_run_names_the_destination() -> None:
    st = FakeStreamlit()

    assert _active_run(st) is None
    assert any("Monte a primeira" in message for message in st.infos)


def test_the_shortcut_button_moves_the_user_to_the_start_screen() -> None:
    """Clicking the button runs the callback, which sets pilot_page."""

    st = FakeStreamlit()
    st.buttons_clicked.add("Montar a semana")

    assert _active_run(st) is None
    assert st.session_state["pilot_page"] == "Preparar"


def test_not_clicking_the_button_leaves_pilot_page_untouched() -> None:
    """When the button is not clicked, pilot_page is not modified."""

    st = FakeStreamlit()

    assert _active_run(st) is None
    assert "pilot_page" not in st.session_state


def test_an_active_run_passes_through_untouched() -> None:
    st = FakeStreamlit({"active_run_id": "run-1"})

    assert _active_run(st) == "run-1"
    assert st.infos == []
