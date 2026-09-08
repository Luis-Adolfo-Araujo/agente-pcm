"""Mapeamento explícito de linhas Tractian para contratos canônicos.

O modo padrão continua estrito e propaga qualquer erro de contrato. A extração do
piloto pode fornecer um :class:`MappingReport`; nesse modo, registros inválidos são
contabilizados sem copiar valores de origem para logs ou metadados.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from domain.planning.entities import (
    AvailabilitySlot,
    ExistingAssignment,
    HistoricalExecution,
    InventoryPosition,
    MaterialRequirement,
    TimeWindow,
    WorkerProfile,
    WorkOrderOperation,
)

_MAPPING_ERRORS = (KeyError, TypeError, ValueError, OverflowError, ValidationError)


@dataclass
class MappingReport:
    """Contadores sanitizados de registros rejeitados durante uma extração."""

    rejected_by_domain: dict[str, int] = field(default_factory=dict)
    rejected_by_error: dict[str, int] = field(default_factory=dict)

    def reject(self, domain: str, error: Exception) -> None:
        self.rejected_by_domain[domain] = self.rejected_by_domain.get(domain, 0) + 1
        error_name = type(error).__name__
        self.rejected_by_error[error_name] = self.rejected_by_error.get(error_name, 0) + 1

    def as_metadata(self) -> dict[str, object]:
        return {
            "rejected_records": sum(self.rejected_by_domain.values()),
            "rejected_by_domain": dict(sorted(self.rejected_by_domain.items())),
            "rejected_by_error": dict(sorted(self.rejected_by_error.items())),
        }


def _source_priority_level(value: Any) -> int | None:
    """Convert Tractian's ascending importance order to the canonical level.

    In the source, ``4`` is "Muito elevado" and ``1`` is "Baixo".  The
    canonical contract intentionally uses the inverse convention: level ``1``
    is the most urgent and level ``4`` is the least urgent.
    """

    if value is None:
        return None
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return None
    return 5 - numeric if 1 <= numeric <= 4 else None


def _source_criticality(value: Any) -> int | None:
    """Normalize Tractian sensitivity (0..5) to the canonical 0..100 scale."""

    if value is None:
        return None
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return None
    if not 0 <= numeric <= 5:
        return None
    return numeric * 20


def map_operations(
    rows: Iterable[Mapping[str, Any]],
    requirements: Mapping[str, tuple[MaterialRequirement, ...]],
    *,
    report: MappingReport | None = None,
) -> tuple[WorkOrderOperation, ...]:
    mapped: list[WorkOrderOperation] = []
    for row in rows:
        try:
            payload = dict(row)
            payload["priority_level"] = _source_priority_level(
                payload.pop("source_priority_order", None)
            )
            payload["criticality"] = _source_criticality(
                payload.pop("source_criticality_sensitivity", None)
            )
            payload["required_materials"] = requirements.get(str(row["operation_id"]), ())
            mapped.append(WorkOrderOperation.model_validate(payload))
        except _MAPPING_ERRORS as error:
            if report is None:
                raise
            report.reject("operations", error)
    return tuple(mapped)


def map_requirements(
    rows: Iterable[Mapping[str, Any]],
    *,
    report: MappingReport | None = None,
) -> dict[str, tuple[MaterialRequirement, ...]]:
    grouped: dict[str, list[MaterialRequirement]] = {}
    for row in rows:
        try:
            grouped.setdefault(str(row["operation_id"]), []).append(
                MaterialRequirement(
                    item_id=str(row["item_id"]),
                    quantity=float(row["quantity"]),
                    reserved_quantity=float(row.get("reserved_quantity") or 0),
                )
            )
        except _MAPPING_ERRORS as error:
            if report is None:
                raise
            report.reject("material_requirements", error)
    return {key: tuple(value) for key, value in grouped.items()}


def map_inventory(
    rows: Iterable[Mapping[str, Any]],
    *,
    report: MappingReport | None = None,
) -> tuple[InventoryPosition, ...]:
    mapped: list[InventoryPosition] = []
    for row in rows:
        try:
            mapped.append(InventoryPosition.model_validate(dict(row)))
        except _MAPPING_ERRORS as error:
            if report is None:
                raise
            report.reject("inventory", error)
    return tuple(mapped)


def map_history(
    rows: Iterable[Mapping[str, Any]],
    *,
    report: MappingReport | None = None,
) -> tuple[HistoricalExecution, ...]:
    mapped: list[HistoricalExecution] = []
    for row in rows:
        try:
            payload = dict(row)
            payload["worker_ids"] = tuple(
                str(value) for value in payload.get("worker_ids") or ()
            )
            mapped.append(HistoricalExecution.model_validate(payload))
        except _MAPPING_ERRORS as error:
            if report is None:
                raise
            report.reject("history", error)
    return tuple(mapped)


def map_workers(
    rows: Iterable[Mapping[str, Any]],
    *,
    report: MappingReport | None = None,
) -> tuple[WorkerProfile, ...]:
    mapped: list[WorkerProfile] = []
    for row in rows:
        try:
            mapped.append(
                WorkerProfile(
                    worker_id=str(row["worker_id"]),
                    team_ids=tuple(str(value) for value in row.get("team_ids") or ()),
                )
            )
        except _MAPPING_ERRORS as error:
            if report is None:
                raise
            report.reject("workers", error)
    return tuple(mapped)


def map_availability(
    rows: Iterable[Mapping[str, Any]],
    *,
    report: MappingReport | None = None,
) -> tuple[AvailabilitySlot, ...]:
    mapped: list[AvailabilitySlot] = []
    for row in rows:
        try:
            mapped.append(
                AvailabilitySlot(
                    worker_id=str(row["worker_id"]),
                    window=TimeWindow(start=row["start"], end=row["end"]),
                )
            )
        except _MAPPING_ERRORS as error:
            if report is None:
                raise
            report.reject("availability", error)
    return tuple(mapped)


def map_assignments(
    rows: Iterable[Mapping[str, Any]],
    *,
    report: MappingReport | None = None,
) -> tuple[ExistingAssignment, ...]:
    mapped: list[ExistingAssignment] = []
    for row in rows:
        try:
            mapped.append(
                ExistingAssignment(
                    operation_id=str(row["operation_id"]),
                    worker_id=str(row["worker_id"]),
                    window=TimeWindow(start=row["start"], end=row["end"]),
                )
            )
        except _MAPPING_ERRORS as error:
            if report is None:
                raise
            report.reject("assignments", error)
    return tuple(mapped)


def snapshot_identity(tenant_id: str, latest_ingestion: datetime, count: int) -> str:
    return f"tractian:{tenant_id}:{latest_ingestion.isoformat()}:{count}"
