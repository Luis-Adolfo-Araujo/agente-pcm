from __future__ import annotations

from presentation.view_models import coverage_view

_PAYLOAD = {
    "coverage": {
        "total_operations": 1200,
        "scheduled_operations": 469,
        "unscheduled_operations": 731,
        "capacity_limited_operations": 529,
        "demand_minutes": 120000,
        "available_minutes": 52800,
        "coverage_percent": 39.1,
        "reasons": {"no_capacity": 529, "blocked": 64, "material": 138},
    }
}


def test_coverage_view_translates_minutes_into_hours_for_the_planner() -> None:
    view = coverage_view(_PAYLOAD)

    assert view["demanda_hh"] == 2000.0
    assert view["disponível_hh"] == 880.0
    assert view["cobertura_percent"] == 39.1


def test_coverage_view_states_how_many_are_a_physical_limit() -> None:
    view = coverage_view(_PAYLOAD)

    assert view["limite_de_capacidade"] == 529
    assert view["outros_motivos"] == 202
    assert "capacidade" in view["leitura"].lower()


def test_coverage_view_survives_a_payload_without_coverage() -> None:
    view = coverage_view({"assignments": []})

    assert view["cobertura_percent"] == 0.0
    assert view["limite_de_capacidade"] == 0
