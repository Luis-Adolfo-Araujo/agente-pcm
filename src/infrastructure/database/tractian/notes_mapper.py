"""Traduz solicitações da Tractian para o contrato canônico de nota."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import ValidationError

from domain.notes.entities import MaintenanceNote
from infrastructure.database.tractian.mapper import MappingReport

_MAPPING_ERRORS = (KeyError, TypeError, ValueError, OverflowError, ValidationError)
_SOURCE = "tractian"
_PRESERVED_FIELDS = ("number", "status")


def map_notes(
    rows: Iterable[Mapping[str, Any]],
    *,
    tenant_id: str,
    report: MappingReport,
) -> tuple[MaintenanceNote, ...]:
    """Mapeia solicitações válidas e contabiliza as rejeitadas.

    ``work_requests`` não possui tipo de nota nem prioridade; os campos ficam
    ausentes em vez de receber um valor inventado.
    """

    notes: list[MaintenanceNote] = []
    for row in rows:
        try:
            notes.append(
                MaintenanceNote(
                    note_id=str(row["note_id"] or ""),
                    tenant_id=tenant_id,
                    source=_SOURCE,
                    created_at=row["created_at"],
                    title=str(row.get("title") or ""),
                    description=str(row.get("description") or ""),
                    asset_id=(
                        str(row["asset_id"]) if row.get("asset_id") is not None else None
                    ),
                    status=(
                        str(row["status"]) if row.get("status") is not None else None
                    ),
                    source_fields={
                        name: str(row[name])
                        for name in _PRESERVED_FIELDS
                        if row.get(name) is not None
                    },
                )
            )
        except _MAPPING_ERRORS as error:
            report.reject("work_requests", error)
    return tuple(notes)


__all__ = ["map_notes"]
