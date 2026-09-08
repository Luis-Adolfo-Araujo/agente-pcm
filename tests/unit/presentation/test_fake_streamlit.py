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


def test_sidebar_is_a_context_manager_that_records_drawn_content() -> None:
    st = FakeStreamlit()

    with st.sidebar:
        st.metric("Sidebar Metric", 42)
        st.info("Sidebar Info")

    assert st.metrics == [("Sidebar Metric", 42)]
    assert st.infos == ["Sidebar Info"]
