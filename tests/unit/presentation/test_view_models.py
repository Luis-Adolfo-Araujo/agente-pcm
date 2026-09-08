from __future__ import annotations

from datetime import UTC, datetime

from presentation.view_models import (
    backlog_rows,
    duration_rows,
    filter_backlog,
    material_rows,
    operation_detail,
    quality_rows,
    run_status_view,
    snapshot_rows,
    to_plain,
    trace_rows,
    unscheduled_rows,
    verification_view,
)


def _item(
    operation_id: str,
    score: float,
    *,
    scheduled: bool = True,
    material_status: str = "available",
    blocking: bool = False,
    reason_codes: tuple[str, ...] = ("SLA_APPROACHING",),
    sla_raw: float = 3.0,
) -> dict[str, object]:
    return {
        "operation": {
            "work_order_id": f"wo-{operation_id}",
            "operation_id": operation_id,
            "title": f"Tarefa {operation_id}",
            "priority_level": 1,
            "criticality": None,
            "asset_id": "asset-1",
            "location_id": "area-1",
            "planned_duration_minutes": 60,
            "due_at": "2026-08-20T00:00:00+00:00",
        },
        "priority": {
            "score": score,
            "band": "high",
            "model": "model_a",
            "reason_codes": list(reason_codes),
            "components": [
                {
                    "name": "age",
                    "raw_value": 12.0,
                    "normalized_value": 13.0,
                    "weight": 0.25,
                    "contribution": 3.0,
                },
                {
                    "name": "sla",
                    "raw_value": sla_raw,
                    "normalized_value": 46.0,
                    "weight": 0.4,
                    "contribution": 18.0,
                },
            ],
        },
        "duration": {
            "minutes": 90,
            "p50_minutes": 80,
            "p80_minutes": 120,
            "source": "same_asset",
            "sample_size": 7,
            "confidence": 0.6,
            "reason_codes": ["DURATION_FROM_HISTORY"],
        },
        "materials": {
            "status": material_status,
            "blocking": blocking,
            "reason_codes": ["MATERIAL_OK"],
            "lines": [],
        },
        "executants": [
            {
                "worker_id": "worker-1",
                "score": 70.0,
                "eligible": True,
                "available_minutes": 480,
                "reason_codes": ["ASSET_EXPERIENCE"],
            }
        ],
        "scheduled": scheduled,
    }


_BACKLOG = {
    "backlog": [
        _item("op-low", 20.0),
        _item("op-high", 90.0, reason_codes=("SLA_OVERDUE",), sla_raw=-4.0),
        _item("op-mid", 55.0, scheduled=False, material_status="unavailable", blocking=True),
    ]
}


def test_to_plain_normalizes_datetimes_for_the_interface() -> None:
    moment = datetime(2026, 8, 18, 9, tzinfo=UTC)

    assert to_plain({"quando": moment})["quando"] == moment.isoformat()


def test_backlog_is_ordered_by_score_regardless_of_input_order() -> None:
    rows = backlog_rows(_BACKLOG)

    assert [row["operação"] for row in rows] == ["op-high", "op-mid", "op-low"]
    assert [row["posição"] for row in rows] == [1, 2, 3]


def test_missing_criticality_is_shown_as_not_informed_never_as_low() -> None:
    rows = backlog_rows(_BACKLOG)

    assert rows[0]["criticidade"] == "Não informada"


def test_overdue_sla_is_described_in_days_late() -> None:
    rows = backlog_rows(_BACKLOG)

    assert rows[0]["vencida"] is True
    assert "Vencida há 4.0 dia" in rows[0]["sla"]


def test_blocking_material_marks_the_operation_as_pending() -> None:
    blocked = next(row for row in backlog_rows(_BACKLOG) if row["operação"] == "op-mid")

    assert blocked["prontidão"] == "Bloqueada"
    assert blocked["material"] == "unavailable"


def test_filter_keeps_only_overdue_when_asked() -> None:
    rows = filter_backlog(backlog_rows(_BACKLOG), overdue_only=True)

    assert [row["operação"] for row in rows] == ["op-high"]


def test_filter_by_scheduling_state_separates_the_two_groups() -> None:
    unscheduled = filter_backlog(backlog_rows(_BACKLOG), scheduled=False)

    assert [row["operação"] for row in unscheduled] == ["op-mid"]


def test_filter_by_material_status_narrows_the_list() -> None:
    rows = filter_backlog(backlog_rows(_BACKLOG), material_statuses={"unavailable"})

    assert [row["operação"] for row in rows] == ["op-mid"]


def test_operation_detail_finds_the_selected_row() -> None:
    detail = operation_detail(_BACKLOG, "op-mid")

    assert detail["operation"]["operation_id"] == "op-mid"


def test_operation_detail_of_an_unknown_id_is_empty() -> None:
    assert operation_detail(_BACKLOG, "nao-existe") == {}


def test_duration_rows_expose_the_divergence_against_the_planned_value() -> None:
    rows = duration_rows(_BACKLOG)

    assert rows[0]["planejada_min"] == 60
    assert rows[0]["adotada_min"] == 90
    assert rows[0]["divergência_%"] == 50.0


def test_material_rows_are_produced_for_every_operation() -> None:
    assert len(material_rows(_BACKLOG)) >= 1


def test_unscheduled_rows_are_sorted_by_priority_and_carry_next_action() -> None:
    schedule = {
        "unscheduled": [
            {
                "work_order_id": "wo-op-low",
                "operation_id": "op-low",
                "reason": "no_capacity",
                "details": ["sem HH"],
            },
            {
                "work_order_id": "wo-op-high",
                "operation_id": "op-high",
                "reason": "material",
                "details": [],
            },
        ]
    }

    rows = unscheduled_rows(schedule, _BACKLOG)

    assert [row["operação"] for row in rows] == ["op-high", "op-low"]
    assert rows[0]["próxima_ação"]


def test_verification_view_counts_only_error_severity() -> None:
    view = verification_view(
        {
            "valid": False,
            "input_hash": "a" * 64,
            "violations": [
                {"code": "X", "severity": "error", "details": "d"},
                {"code": "Y", "severity": "warning", "details": "d"},
            ],
        }
    )

    assert view["valid"] is False
    assert view["error_count"] == 1
    assert len(view["violations"]) == 2


def test_run_status_view_reads_the_current_state() -> None:
    view = run_status_view(
        {"run_id": "run-1", "status": "running", "current_stage": "optimization"}
    )

    assert view["status"] == "running"


def test_trace_rows_are_ordered_by_stage_sequence() -> None:
    rows = trace_rows(
        {
            "trace_events": [
                {"sequence": 2, "stage": "skills_parallel", "elapsed_ms": 20, "counts": {"a": 1}},
                {"sequence": 1, "stage": "snapshot_validated", "elapsed_ms": 10, "counts": {}},
            ]
        }
    )

    assert [row["etapa"] for row in rows] == ["snapshot_validated", "skills_parallel"]


def test_quality_rows_render_persisted_indicators() -> None:
    rows = quality_rows(
        {
            "snapshot_id": "snap-1",
            "quality": {
                "indicators": [
                    {
                        "key": "operations_with_priority",
                        "present": 9,
                        "total": 10,
                        "missing": 1,
                        "coverage_percent": 90.0,
                    }
                ]
            },
        }
    )

    assert rows[0]["valor"] == 90.0
    assert rows[0]["afetados"] == 1


def test_quality_rows_of_a_snapshot_without_indicators_is_empty() -> None:
    assert quality_rows({"snapshot_id": "snap-1"}) == []


def test_unknown_material_is_never_displayed_as_ready() -> None:
    """Sem cadastro de material a prontidão é desconhecida, não afirmada."""

    payload = {
        "backlog": [
            _item("op-sem-material", 50.0, material_status="unknown", blocking=False)
        ]
    }

    row = backlog_rows(payload)[0]

    assert row["prontidão"] == "Sem informação"


def test_blocking_material_still_reads_as_blocked() -> None:
    payload = {
        "backlog": [
            _item("op-bloqueada", 50.0, material_status="unavailable", blocking=True)
        ]
    }

    assert backlog_rows(payload)[0]["prontidão"] == "Bloqueada"


def test_available_material_reads_as_ready() -> None:
    payload = {"backlog": [_item("op-ok", 50.0, material_status="available")]}

    assert backlog_rows(payload)[0]["prontidão"] == "Pronta"


def test_snapshot_rows_read_counts_from_the_quality_block() -> None:
    """SnapshotSummary publica os contadores dentro de quality, não na raiz."""

    rows = snapshot_rows(
        [
            {
                "snapshot_id": "snap-1",
                "tenant_id": "planta-modelo",
                "as_of": "2026-08-17T12:00:00+00:00",
                "quality": {
                    "operation_count": 1200,
                    "worker_count": 22,
                    "inventory_item_count": 1800,
                },
            }
        ]
    )

    assert rows[0]["operações"] == 1200
    assert rows[0]["pessoas"] == 22
    assert rows[0]["materiais"] == 1800


def test_snapshot_rows_fall_back_to_not_informed_without_counts() -> None:
    rows = snapshot_rows([{"snapshot_id": "snap-1"}])

    assert rows[0]["operações"] == "Não informado"
