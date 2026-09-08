"""Contratos canônicos do tratamento de notas.

Os modelos são imutáveis e rejeitam campos desconhecidos, como no planejamento,
para que um lote e seu resultado sejam reproduzíveis e auditáveis.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone")
    return value


class DuplicateVerdict(StrEnum):
    UNIQUE = "unique"
    DUPLICATE = "duplicate"
    NEEDS_REVIEW = "needs_review"


class SuggestionOrigin(StrEnum):
    REGISTERED = "registered"
    DERIVED_RULE = "derived_rule"
    INFERRED_MODEL = "inferred_model"


class FieldPolicy(StrEnum):
    ADVISORY = "advisory"
    AUTHORITATIVE = "authoritative"
    RECOMMENDATION = "recommendation"


class MaintenanceNote(ContractModel):
    """Nota de manutenção agnóstica de fonte."""

    note_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    created_at: datetime
    title: str = ""
    description: str = ""
    asset_id: str | None = None
    location_id: str | None = None
    note_type: str | None = None
    priority_level: int | None = Field(default=None, ge=1, le=4)
    status: str | None = None
    # Preserva as colunas originais para que a saída devolva o arquivo íntegro.
    source_fields: dict[str, str] = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def created_requires_timezone(cls, value: datetime) -> datetime:
        return _ensure_aware(value)

    @property
    def comparable_text(self) -> str:
        return f"{self.title} {self.description}".strip()


class NoteBatch(ContractModel):
    schema_version: str = "1.0"
    batch_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    as_of: datetime
    notes: tuple[MaintenanceNote, ...]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("as_of")
    @classmethod
    def as_of_requires_timezone(cls, value: datetime) -> datetime:
        return _ensure_aware(value)

    @model_validator(mode="after")
    def unique_note_ids(self) -> NoteBatch:
        identifiers = [item.note_id for item in self.notes]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("note_id must be unique inside a batch")
        return self


class DuplicateAssessment(ContractModel):
    note_id: str
    verdict: DuplicateVerdict
    duplicate_of: str | None = None
    score: float = Field(ge=0, le=1)
    adjudicated: bool = False
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def a_duplicate_points_at_its_original(self) -> DuplicateAssessment:
        if self.verdict is DuplicateVerdict.DUPLICATE and not self.duplicate_of:
            raise ValueError("a duplicate must reference the original note")
        if self.verdict is DuplicateVerdict.UNIQUE and self.duplicate_of:
            raise ValueError("a unique note cannot reference an original")
        return self


class FieldSuggestion(ContractModel):
    field: str = Field(min_length=1)
    value: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    origin: SuggestionOrigin
    policy: FieldPolicy
    catalog_valid: bool = False
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def an_absent_value_explains_itself(self) -> FieldSuggestion:
        if self.value is None and not self.reason_codes:
            raise ValueError("an omitted suggestion must carry a structured reason")
        return self


class NoteAssessment(ContractModel):
    note_id: str
    duplicate: DuplicateAssessment
    suggestions: tuple[FieldSuggestion, ...] = ()


class NoteBatchResult(ContractModel):
    schema_version: str = "1.0"
    batch_id: str
    tenant_id: str
    as_of: datetime
    ruleset_version: str
    config_hash: str
    adjudicator: str
    assessments: tuple[NoteAssessment, ...]

    @field_validator("as_of")
    @classmethod
    def result_as_of_requires_timezone(cls, value: datetime) -> datetime:
        return _ensure_aware(value)


__all__ = [
    "ContractModel",
    "DuplicateAssessment",
    "DuplicateVerdict",
    "FieldPolicy",
    "FieldSuggestion",
    "MaintenanceNote",
    "NoteAssessment",
    "NoteBatch",
    "NoteBatchResult",
    "SuggestionOrigin",
]
