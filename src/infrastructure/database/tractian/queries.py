"""Consultas do adaptador Tractian.

Somente este módulo conhece nomes e unidades do schema de origem.
"""

SNAPSHOT_INFO_SQL = """
WITH source_watermarks AS (
    SELECT max(data_ingestao) AS ingested_at
    FROM tractian.work_orders WHERE company_id = %(tenant_id)s
    UNION ALL
    SELECT max(data_ingestao)
    FROM tractian.work_order_operations WHERE company_id = %(tenant_id)s
    UNION ALL
    SELECT max(data_ingestao)
    FROM tractian.work_order_priorities WHERE company_id = %(tenant_id)s
    UNION ALL
    SELECT max(data_ingestao)
    FROM tractian.assets WHERE company_id = %(tenant_id)s
    UNION ALL
    SELECT max(data_ingestao)
    FROM tractian.asset_criticalities WHERE company_id = %(tenant_id)s
    UNION ALL
    SELECT max(data_ingestao)
    FROM tractian.supply_work_order_items WHERE company_id = %(tenant_id)s
    UNION ALL
    SELECT max(data_ingestao)
    FROM tractian.supply_items WHERE company_id = %(tenant_id)s
    UNION ALL
    SELECT max(data_ingestao)
    FROM tractian.supply_item_storage WHERE company_id = %(tenant_id)s
    UNION ALL
    SELECT max(data_ingestao)
    FROM tractian.work_order_elapsed_intervals WHERE company_id = %(tenant_id)s
    UNION ALL
    SELECT max(data_ingestao)
    FROM tractian.work_order_operation_executants WHERE company_id = %(tenant_id)s
    UNION ALL
    SELECT max(data_ingestao)
    FROM tractian.users WHERE company_id = %(tenant_id)s
    UNION ALL
    SELECT max(data_ingestao)
    FROM tractian.team_users WHERE company_id = %(tenant_id)s
    UNION ALL
    SELECT max(data_ingestao)
    FROM tractian.analytical_user_available_time WHERE company_id = %(tenant_id)s
    UNION ALL
    SELECT max(data_ingestao)
    FROM tractian.calendar_schedules WHERE company_id = %(tenant_id)s
    UNION ALL
    SELECT max(data_ingestao)
    FROM tractian.calendar_schedule_participants WHERE company_id = %(tenant_id)s
)
SELECT
    (SELECT max(ingested_at) FROM source_watermarks) AS latest_ingestion,
    count(*) FILTER (WHERE NOT deleted) AS work_order_count
FROM tractian.work_orders
WHERE company_id = %(tenant_id)s
"""

OPERATIONS_SQL = """
SELECT
    w.id AS work_order_id,
    coalesce(o.id, w.id || ':default') AS operation_id,
    coalesce(nullif(o.title, ''), w.title) AS title,
    w.status,
    w.planning_status,
    w.created_at,
    w.due_date AS due_at,
    p."order" AS source_priority_order,
    c.sensitivity AS source_criticality_sensitivity,
    coalesce(o.asset_id, w.asset_id) AS asset_id,
    coalesce(o.location_id, w.location_id) AS location_id,
    o.activity_type_id,
    o.planned_team_id,
    CASE
      WHEN o.planned_working_time > 0
      THEN greatest(1, round(o.planned_working_time / 60.0)::integer)
      ELSE NULL
    END AS planned_duration_minutes,
    greatest(1, coalesce(o.planned_worker_number, 1)) AS required_worker_count,
    (w.status = 'onHold' OR w.on_hold_reason_id IS NOT NULL) AS blocked,
    w.on_hold_reason_id AS block_reason
FROM tractian.work_orders w
LEFT JOIN tractian.work_order_operations o
       ON o.work_order_id = w.id
      AND o.company_id = w.company_id
      AND NOT o.deleted
LEFT JOIN tractian.work_order_priorities p
       ON p.id = w.priority_id
      AND p.company_id = w.company_id
LEFT JOIN tractian.assets a
       ON a.id = coalesce(o.asset_id, w.asset_id)
      AND a.company_id = w.company_id
      AND NOT a.deleted
LEFT JOIN tractian.asset_criticalities c
       ON c.id = a.criticality_id
      AND c.company_id = w.company_id
      AND NOT c.deleted
WHERE w.company_id = %(tenant_id)s
  AND NOT w.deleted
  AND w.created_at <= %(as_of)s
  AND w.status IN ('open', 'inProgress', 'onHold')
ORDER BY w.id, operation_id
"""

MATERIAL_REQUIREMENTS_SQL = """
SELECT
    coalesce(nullif(m.work_order_operation_oid, ''), m.work_order_oid || ':default')
        AS operation_id,
    m.item_id::text AS item_id,
    sum(m.quantity)::double precision AS quantity,
    sum(CASE WHEN m.status = 'reserved' THEN m.quantity ELSE 0 END)::double precision
        AS reserved_quantity
FROM tractian.supply_work_order_items m
JOIN tractian.work_orders w
  ON w.id = m.work_order_oid
 AND w.company_id = m.company_id
 AND NOT w.deleted
WHERE m.company_id = %(tenant_id)s
  AND NOT m.deleted
  AND m.status IN ('notReserved', 'pendingApproval', 'reserved')
  AND w.created_at <= %(as_of)s
  AND w.status IN ('open', 'inProgress', 'onHold')
GROUP BY 1, 2
HAVING sum(m.quantity) > 0
"""

INVENTORY_SQL = """
SELECT
    i.id::text AS item_id,
    greatest(
        0,
        coalesce(sum(s.available_quantity + s.reserved_quantity), 0)
    )::double precision AS on_hand_quantity,
    greatest(0, coalesce(sum(s.reserved_quantity), 0))::double precision
        AS reserved_quantity,
    max(i.lead_time) AS lead_time_days
FROM tractian.supply_items i
LEFT JOIN tractian.supply_item_storage s
       ON s.item_id = i.id
      AND s.company_id = i.company_id
      AND NOT s.deleted
WHERE i.company_id = %(tenant_id)s
  AND NOT i.deleted
  AND NOT i.disabled
GROUP BY i.id
"""

HISTORY_SQL = """
WITH single_operation_orders AS (
    SELECT work_order_id
    FROM tractian.work_order_operations
    WHERE company_id = %(tenant_id)s AND NOT deleted
    GROUP BY work_order_id
    HAVING count(*) = 1
), elapsed AS (
    SELECT
        work_order_id,
        max(ended_at) AS finished_at,
        greatest(1, round(sum(duration_in_seconds) / 60.0)::integer) AS duration_minutes
    FROM tractian.work_order_elapsed_intervals
    WHERE company_id = %(tenant_id)s
      AND status = 'inProgress'
    GROUP BY work_order_id
    HAVING bool_and(
        started_at IS NOT NULL
        AND ended_at IS NOT NULL
        AND ended_at > started_at
        AND ended_at <= %(as_of)s
        AND duration_in_seconds > 0
        AND duration_in_seconds <= 86400
    )
), workers AS (
    SELECT operation_id, array_agg(DISTINCT executant_id ORDER BY executant_id) AS worker_ids
    FROM tractian.work_order_operation_executants
    WHERE company_id = %(tenant_id)s
    GROUP BY operation_id
)
SELECT
    w.id AS work_order_id,
    o.id AS operation_id,
    coalesce(nullif(o.title, ''), w.title) AS title,
    e.finished_at,
    e.duration_minutes,
    wk.worker_ids,
    w.asset_id,
    w.location_id,
    o.activity_type_id,
    o.planned_team_id AS team_id
FROM elapsed e
JOIN single_operation_orders s ON s.work_order_id = e.work_order_id
JOIN tractian.work_orders w ON w.id = e.work_order_id
JOIN tractian.work_order_operations o
  ON o.work_order_id = w.id
 AND o.company_id = w.company_id
 AND NOT o.deleted
LEFT JOIN workers wk ON wk.operation_id = o.id
WHERE w.company_id = %(tenant_id)s
  AND NOT w.deleted
  AND w.status = 'closed'
  AND o.status = 'finished'
  AND o.finished_at IS NOT NULL
  AND o.finished_at <= %(as_of)s
ORDER BY e.finished_at, o.id
"""

WORKERS_SQL = """
WITH candidate_workers AS (
    SELECT executant_id AS worker_id
    FROM tractian.work_order_operation_executants
    WHERE company_id = %(tenant_id)s
    UNION
    SELECT user_id AS worker_id
    FROM tractian.analytical_user_available_time
    WHERE company_id = %(tenant_id)s
      AND dt_end > %(period_start)s
      AND dt_start < %(period_end)s
)
SELECT
    u.id AS worker_id,
    coalesce(
        array_agg(DISTINCT tu.team_id ORDER BY tu.team_id)
            FILTER (WHERE tu.team_id IS NOT NULL),
        ARRAY[]::text[]
    ) AS team_ids
FROM tractian.users u
JOIN candidate_workers candidate ON candidate.worker_id = u.id
LEFT JOIN tractian.team_users tu
       ON tu.user_id = u.id
      AND tu.company_id = u.company_id
WHERE u.company_id = %(tenant_id)s AND NOT u.deleted
GROUP BY u.id
ORDER BY u.id
"""

AVAILABILITY_SQL = """
SELECT user_id AS worker_id, dt_start AS start, dt_end AS end
FROM tractian.analytical_user_available_time
WHERE company_id = %(tenant_id)s
  AND dt_end > dt_start
  AND dt_end > %(period_start)s
  AND dt_start < %(period_end)s
ORDER BY user_id, dt_start
"""

EXISTING_ASSIGNMENTS_SQL = """
SELECT
    coalesce(cs.work_order_operation_id, cs.id) AS operation_id,
    cp.participant_id AS worker_id,
    cp.start_at AS start,
    cp.end_at AS end
FROM tractian.calendar_schedule_participants cp
JOIN tractian.calendar_schedules cs
  ON cs.id = cp.calendar_schedule_id
 AND cs.company_id = cp.company_id
WHERE cp.company_id = %(tenant_id)s
  AND NOT cp.deleted
  AND NOT cs.deleted
  AND cp.participant_type = 'user'
  AND cp.participant_id IS NOT NULL
  AND cp.start_at IS NOT NULL
  AND cp.end_at IS NOT NULL
  AND cp.end_at > cp.start_at
  AND cp.end_at > %(period_start)s
  AND cp.start_at < %(period_end)s
ORDER BY cp.participant_id, cp.start_at
"""


WORK_REQUESTS_SQL = """
SELECT
    r.id AS note_id,
    r.number,
    r.created_at,
    r.title,
    r.description,
    r.asset_id,
    r.status
FROM tractian.work_requests r
WHERE r.company_id = %(tenant_id)s
  AND coalesce(r.deleted, false) = false
  AND r.created_at <= %(as_of)s
ORDER BY r.created_at, r.id
"""
