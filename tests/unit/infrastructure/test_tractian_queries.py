from infrastructure.database.tractian import queries


def compact(sql: str) -> str:
    return " ".join(sql.split())


def test_operation_query_exposes_source_scales_and_converts_seconds_to_minutes() -> None:
    sql = compact(queries.OPERATIONS_SQL)

    assert 'p."order" AS source_priority_order' in sql
    assert "c.sensitivity AS source_criticality_sensitivity" in sql
    assert "o.planned_working_time / 60.0" in sql
    assert "coalesce(o.asset_id, w.asset_id) AS asset_id" in sql
    assert "coalesce(o.location_id, w.location_id) AS location_id" in sql
    assert "o.company_id = w.company_id" in sql
    assert "p.company_id = w.company_id" in sql
    assert "c.company_id = w.company_id" in sql
    assert "w.created_at <= %(as_of)s" in sql


def test_history_uses_completed_execution_intervals_without_future_leakage() -> None:
    sql = compact(queries.HISTORY_SQL)

    assert "status = 'inProgress'" in sql
    assert "duration_in_seconds) / 60.0" in sql
    assert "ended_at <= %(as_of)s" in sql
    assert "duration_in_seconds <= 86400" in sql
    assert "HAVING bool_and" in sql
    assert "w.status = 'closed'" in sql
    assert "o.status = 'finished'" in sql
    assert "o.finished_at <= %(as_of)s" in sql


def test_material_query_returns_pending_and_reserved_active_requirements() -> None:
    sql = compact(queries.MATERIAL_REQUIREMENTS_SQL)

    assert "m.item_id::text AS item_id" in sql
    assert "m.status IN ('notReserved', 'pendingApproval', 'reserved')" in sql
    assert "m.status = 'reserved'" in sql
    assert "w.created_at <= %(as_of)s" in sql
    assert "w.status IN ('open', 'inProgress', 'onHold')" in sql
    assert "HAVING sum(m.quantity) > 0" in sql


def test_inventory_preserves_source_net_available_quantity() -> None:
    sql = compact(queries.INVENTORY_SQL)

    # Canonical net = on_hand - reserved, so expressing on_hand as
    # source.available + source.reserved preserves Tractian's authoritative net.
    assert "sum(s.available_quantity + s.reserved_quantity)" in sql
    assert "sum(s.reserved_quantity)" in sql
    assert "s.company_id = i.company_id" in sql


def test_people_and_calendar_queries_are_tenant_scoped_and_reject_bad_windows() -> None:
    workers_sql = compact(queries.WORKERS_SQL)
    availability_sql = compact(queries.AVAILABILITY_SQL)
    assignments_sql = compact(queries.EXISTING_ASSIGNMENTS_SQL)

    assert "ARRAY[]::text[]" in workers_sql
    assert "tu.company_id = u.company_id" in workers_sql
    assert "dt_end > dt_start" in availability_sql
    assert "cs.company_id = cp.company_id" in assignments_sql
    assert "cp.participant_type = 'user'" in assignments_sql
    assert "cp.end_at > cp.start_at" in assignments_sql


def test_snapshot_watermark_covers_every_current_state_input() -> None:
    sql = compact(queries.SNAPSHOT_INFO_SQL)
    expected_tables = {
        "work_orders",
        "work_order_operations",
        "work_order_priorities",
        "assets",
        "asset_criticalities",
        "supply_work_order_items",
        "supply_items",
        "supply_item_storage",
        "work_order_elapsed_intervals",
        "work_order_operation_executants",
        "users",
        "team_users",
        "analytical_user_available_time",
        "calendar_schedules",
        "calendar_schedule_participants",
    }

    for table in expected_tables:
        assert f"tractian.{table}" in sql
    assert "max(ingested_at)" in sql
