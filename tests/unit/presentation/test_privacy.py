from __future__ import annotations

import json

import pytest

from presentation.privacy import (
    anonymous_access_enabled,
    display_worker_id,
    password_is_valid,
    pseudonymize_export,
    pseudonymize_worker_fields,
    raw_worker_ids_enabled,
    worker_alias,
)


def test_alias_is_stable_for_the_same_worker() -> None:
    assert worker_alias("worker-1") == worker_alias("worker-1")


def test_alias_separates_distinct_workers() -> None:
    assert worker_alias("worker-1") != worker_alias("worker-2")


def test_alias_changes_with_the_configured_salt() -> None:
    assert worker_alias("worker-1", salt="a") != worker_alias("worker-1", salt="b")


def test_alias_never_contains_the_source_identifier() -> None:
    assert "worker-1" not in worker_alias("worker-1")


def test_alias_is_idempotent_so_a_second_pass_does_not_double_hash() -> None:
    once = worker_alias("worker-1")

    assert worker_alias(once) == once


def test_raw_identifiers_require_explicit_opt_in() -> None:
    assert raw_worker_ids_enabled({}) is False
    assert raw_worker_ids_enabled({"MAIA_PILOT_SHOW_RAW_WORKER_IDS": "false"}) is False
    assert raw_worker_ids_enabled({"MAIA_PILOT_SHOW_RAW_WORKER_IDS": "true"}) is True


def test_anonymous_access_requires_its_own_opt_in() -> None:
    assert anonymous_access_enabled({}) is False
    assert anonymous_access_enabled({"MAIA_PILOT_ALLOW_ANONYMOUS": "sim"}) is True


def test_display_reveals_the_source_id_only_when_asked() -> None:
    assert display_worker_id("worker-1", reveal=True) == "worker-1"
    assert display_worker_id("worker-1") != "worker-1"


def test_password_comparison_rejects_a_wrong_secret() -> None:
    assert password_is_valid("segredo", "segredo") is True
    assert password_is_valid("segredo", "errado") is False


def test_pseudonymization_replaces_worker_fields_at_any_depth() -> None:
    payload = {
        "assignments": [
            {"operation_id": "op-1", "worker_ids": ["worker-1", "worker-2"]},
        ],
        "capacities": [{"worker_id": "worker-1", "net_minutes": 480}],
    }

    sanitized = pseudonymize_worker_fields(payload)

    assert "worker-1" not in json.dumps(sanitized)
    assert sanitized["capacities"][0]["net_minutes"] == 480
    assert sanitized["assignments"][0]["operation_id"] == "op-1"


def test_pseudonymization_keeps_candidate_records_whole() -> None:
    """A lista de executantes carrega a saída da skill, não só nomes."""

    payload = {
        "executants": [
            {
                "worker_id": "w-1",
                "score": 91.2,
                "eligible": True,
                "reason_codes": ["TEAM_MATCH"],
            }
        ]
    }

    sanitized = pseudonymize_worker_fields(payload, salt="s")

    candidato = sanitized["executants"][0]
    assert candidato["worker_id"].startswith("Técnico-")
    assert candidato["worker_id"] != "w-1"
    assert candidato["score"] == 91.2
    assert candidato["eligible"] is True
    assert candidato["reason_codes"] == ["TEAM_MATCH"]


def test_pseudonymization_still_aliases_plain_worker_lists() -> None:
    sanitized = pseudonymize_worker_fields({"worker_ids": ["w-1", "w-2"]}, salt="s")

    assert all(item.startswith("Técnico-") for item in sanitized["worker_ids"])
    assert len(set(sanitized["worker_ids"])) == 2


def test_pseudonymization_keeps_non_worker_values_untouched() -> None:
    payload = {"operation_id": "worker-like-op", "title": "Trocar rolamento"}

    assert pseudonymize_worker_fields(payload) == payload


def test_reveal_disables_pseudonymization_entirely() -> None:
    payload = {"worker_id": "worker-1"}

    assert pseudonymize_worker_fields(payload, reveal=True) == payload


def test_csv_export_is_pseudonymized_column_by_column() -> None:
    csv_payload = (
        b"operation_id,worker_ids,priority_score\n" b"op-1,worker-1|worker-2,88.5\n"
    )

    sanitized = pseudonymize_export(csv_payload, "csv").decode("utf-8")

    assert "worker-1" not in sanitized
    assert "op-1" in sanitized
    assert "88.5" in sanitized


def test_json_export_is_pseudonymized_before_download() -> None:
    payload = json.dumps({"worker_ids": ["worker-1"]}).encode("utf-8")

    sanitized = pseudonymize_export(payload, "json").decode("utf-8")

    assert "worker-1" not in sanitized


def test_unsupported_export_format_is_refused_instead_of_leaking() -> None:
    with pytest.raises(ValueError):
        pseudonymize_export(b"anything", "xlsx")
