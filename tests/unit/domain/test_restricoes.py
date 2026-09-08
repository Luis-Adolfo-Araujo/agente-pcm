from datetime import date

from domain.planning.adjustments import PlanningConstraints, apply_constraints
from tests.support.planning import capacities_base, enriched_base, request_base


def test_empty_constraints_change_nothing() -> None:
    enriched, capacities = apply_constraints(
        enriched_base(), capacities_base(), PlanningConstraints(), request_base()
    )
    assert enriched == enriched_base()
    assert capacities == capacities_base()


def test_must_exclude_drops_the_operation() -> None:
    enriched, _ = apply_constraints(
        enriched_base(),
        capacities_base(),
        PlanningConstraints(must_exclude=("op-high",)),
        request_base(),
    )
    assert all(item.operation.operation_id != "op-high" for item in enriched)


def test_blocked_day_removes_that_day_from_capacity() -> None:
    _, capacities = apply_constraints(
        enriched_base(),
        capacities_base(),
        PlanningConstraints(blocked_days=(date(2026, 8, 19),)),
        request_base(),
    )
    for capacity in capacities:
        assert all(slot.window.start.date() != date(2026, 8, 19) for slot in capacity.slots)


def test_worker_asset_block_removes_that_candidate() -> None:
    enriched, _ = apply_constraints(
        enriched_base(),
        capacities_base(),
        PlanningConstraints(worker_asset_blocks=(("w-1", "asset-1"),)),
        request_base(),
    )
    target = next(item for item in enriched if item.operation.asset_id == "asset-1")
    assert all(candidate.worker_id != "w-1" for candidate in target.executants)
