"""Tests for row selection on the ranking table."""

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
