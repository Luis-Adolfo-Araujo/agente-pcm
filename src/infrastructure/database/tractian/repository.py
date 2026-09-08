"""Repositório Tractian somente leitura para gerar snapshots atuais."""

from __future__ import annotations

from datetime import datetime

import psycopg
from psycopg.rows import dict_row

from domain.notes.entities import NoteBatch
from domain.planning.entities import PlanningSnapshot, TimeWindow
from infrastructure.database.tractian import queries
from infrastructure.database.tractian.mapper import (
    MappingReport,
    map_assignments,
    map_availability,
    map_history,
    map_inventory,
    map_operations,
    map_requirements,
    map_workers,
    snapshot_identity,
)
from infrastructure.database.tractian.notes_mapper import map_notes


class TractianPlanningRepository:
    """Ler um snapshot sem realizar escrita no banco de origem."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def load_snapshot(
        self,
        *,
        tenant_id: str,
        as_of: datetime,
        period: TimeWindow,
    ) -> PlanningSnapshot:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must include a timezone")

        params = {
            "tenant_id": tenant_id,
            "as_of": as_of,
            "period_start": period.start,
            "period_end": period.end,
        }
        with psycopg.connect(self._dsn, row_factory=dict_row) as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            info = connection.execute(queries.SNAPSHOT_INFO_SQL, params).fetchone()
            if info is None or info["latest_ingestion"] is None:
                raise ValueError("tenant has no Tractian work-order snapshot")
            latest_ingestion = info["latest_ingestion"]
            if as_of < latest_ingestion:
                raise ValueError(
                    "current-state tables cannot safely reconstruct a historical as_of; "
                    "use an immutable historical snapshot"
                )

            mapping_report = MappingReport()
            requirement_rows = connection.execute(
                queries.MATERIAL_REQUIREMENTS_SQL, params
            ).fetchall()
            requirements = map_requirements(requirement_rows, report=mapping_report)
            operations = map_operations(
                connection.execute(queries.OPERATIONS_SQL, params).fetchall(),
                requirements,
                report=mapping_report,
            )
            inventory = map_inventory(
                connection.execute(queries.INVENTORY_SQL, params).fetchall(),
                report=mapping_report,
            )
            history = map_history(
                connection.execute(queries.HISTORY_SQL, params).fetchall(),
                report=mapping_report,
            )
            workers = map_workers(
                connection.execute(queries.WORKERS_SQL, params).fetchall(),
                report=mapping_report,
            )
            availability = map_availability(
                connection.execute(queries.AVAILABILITY_SQL, params).fetchall(),
                report=mapping_report,
            )
            assignments = map_assignments(
                connection.execute(queries.EXISTING_ASSIGNMENTS_SQL, params).fetchall(),
                report=mapping_report,
            )

        return PlanningSnapshot(
            snapshot_id=snapshot_identity(
                tenant_id,
                latest_ingestion,
                int(info["work_order_count"]),
            ),
            tenant_id=tenant_id,
            as_of=as_of,
            operations=operations,
            history=history,
            inventory=inventory,
            workers=workers,
            availability=availability,
            existing_assignments=assignments,
            metadata={
                "source": "tractian",
                "latest_ingestion": latest_ingestion.isoformat(),
                "historical_reconstruction": False,
                **mapping_report.as_metadata(),
            },
        )


class TractianNoteRepository:
    """Leitura somente de solicitações, isolada do repositório de planejamento."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def load_batch(self, *, tenant_id: str, as_of: datetime) -> NoteBatch:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must include a timezone")
        report = MappingReport()
        with psycopg.connect(self._dsn, row_factory=dict_row) as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            rows = connection.execute(
                queries.WORK_REQUESTS_SQL,
                {"tenant_id": tenant_id, "as_of": as_of},
            ).fetchall()
        notes = map_notes(rows, tenant_id=tenant_id, report=report)
        return NoteBatch(
            batch_id=f"tractian:{tenant_id}:{as_of.isoformat()}:{len(notes)}",
            tenant_id=tenant_id,
            source="tractian",
            as_of=as_of,
            notes=notes,
            metadata={"source": "tractian", **report.as_metadata()},
        )
