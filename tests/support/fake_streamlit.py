"""Dublê de Streamlit para exercitar as telas sem navegador.

As telas recebem o objeto Streamlit por injeção, então um dublê que registra
o que foi desenhado é suficiente para testar a lógica de apresentação.
"""

from __future__ import annotations

import datetime
from typing import Any, Literal


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
        self.markdowns: list[str] = []
        self.subheaders: list[str] = []
        self.codes: list[str] = []
        self.progress_values: list[Any] = []
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

    def markdown(self, body: Any = "", *args: Any, **kwargs: Any) -> None:
        self._record.markdowns.append(str(body))

    def subheader(self, body: Any = "", *args: Any, **kwargs: Any) -> None:
        self._record.subheaders.append(str(body))

    def code(self, body: Any = "", *args: Any, **kwargs: Any) -> None:
        self._record.codes.append(str(body))

    def progress(self, value: Any = 0, *args: Any, **kwargs: Any) -> None:
        self._record.progress_values.append(value)

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
        clicked = str(label) in self._record.buttons_clicked
        if clicked and "on_click" in kwargs:
            kwargs["on_click"]()
        return clicked

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

    @property
    def sidebar(self) -> FakeStreamlit:
        # Property like real Streamlit, unlike other layout methods (container, form, etc.)
        return self

    def __enter__(self) -> FakeStreamlit:
        return self

    def __exit__(self, *args: Any) -> Literal[False]:
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
