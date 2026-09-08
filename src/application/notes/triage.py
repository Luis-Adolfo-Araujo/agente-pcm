"""Triagem determinística de um lote de notas, com adjudicação restrita.

A ordem importa: o bloqueio decide o que é comparável, o score determinístico
resolve os extremos, e só a faixa cinzenta consulta o adjudicador.
"""

from __future__ import annotations

import hashlib
import json

from application.notes.adjudicator import DuplicateAdjudicator
from domain.notes.config import NoteTriageConfig
from domain.notes.duplicates import candidate_pairs, score_pair
from domain.notes.entities import (
    DuplicateAssessment,
    DuplicateVerdict,
    FieldPolicy,
    FieldSuggestion,
    MaintenanceNote,
    NoteAssessment,
    NoteBatch,
    NoteBatchResult,
    SuggestionOrigin,
)

RULESET_VERSION = "notes-triage-v1"


def config_hash(config: NoteTriageConfig) -> str:
    canonical = json.dumps(
        config.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _decide(
    left: MaintenanceNote,
    right: MaintenanceNote,
    score: float,
    config: NoteTriageConfig,
    adjudicator: DuplicateAdjudicator | None,
) -> tuple[DuplicateVerdict, bool, tuple[str, ...]]:
    if score >= config.duplicate_threshold:
        return DuplicateVerdict.DUPLICATE, False, ("deterministic_score_above_threshold",)
    if score < config.review_threshold:
        return DuplicateVerdict.UNIQUE, False, ("deterministic_score_below_threshold",)
    if adjudicator is None:
        return DuplicateVerdict.NEEDS_REVIEW, False, ("adjudicator_unavailable",)
    try:
        adjudicated = adjudicator.is_duplicate(left, right)
    except Exception:  # noqa: BLE001 - indisponibilidade não pode virar unicidade
        return DuplicateVerdict.NEEDS_REVIEW, False, ("adjudicator_failed",)
    if adjudicated:
        return DuplicateVerdict.DUPLICATE, True, ("adjudicated_duplicate",)
    return DuplicateVerdict.UNIQUE, True, ("adjudicated_unique",)


def _note_type_suggestion(
    note: MaintenanceNote,
    config: NoteTriageConfig,
) -> FieldSuggestion:
    if note.note_type:
        return FieldSuggestion(
            field="note_type",
            value=note.note_type,
            confidence=1.0,
            origin=SuggestionOrigin.REGISTERED,
            policy=FieldPolicy.ADVISORY,
            catalog_valid=(
                not config.note_type_catalog or note.note_type in config.note_type_catalog
            ),
            reason_codes=("registered_in_source",),
        )
    if not config.note_type_catalog:
        return FieldSuggestion(
            field="note_type",
            value=None,
            origin=SuggestionOrigin.DERIVED_RULE,
            policy=FieldPolicy.ADVISORY,
            reason_codes=("catalog_not_configured",),
        )
    return FieldSuggestion(
        field="note_type",
        value=None,
        origin=SuggestionOrigin.DERIVED_RULE,
        policy=FieldPolicy.ADVISORY,
        reason_codes=("note_type_absent_in_source",),
    )


def _priority_suggestion(note: MaintenanceNote) -> FieldSuggestion:
    if note.priority_level is not None:
        return FieldSuggestion(
            field="priority_level",
            value=str(note.priority_level),
            confidence=1.0,
            origin=SuggestionOrigin.REGISTERED,
            policy=FieldPolicy.ADVISORY,
            catalog_valid=True,
            reason_codes=("registered_in_source",),
        )
    return FieldSuggestion(
        field="priority_level",
        value=None,
        origin=SuggestionOrigin.DERIVED_RULE,
        policy=FieldPolicy.ADVISORY,
        reason_codes=("no_historical_linkage",),
    )


def treat_notes(
    batch: NoteBatch,
    config: NoteTriageConfig | None = None,
    *,
    adjudicator: DuplicateAdjudicator | None = None,
) -> NoteBatchResult:
    """Avalia duplicidade, tipo de nota e prioridade de um lote."""

    config = config or NoteTriageConfig()
    duplicates: dict[str, DuplicateAssessment] = {}

    for left, right in candidate_pairs(batch.notes, config):
        if right.note_id in duplicates:
            continue
        score = score_pair(left, right, config)
        verdict, adjudicated, reason_codes = _decide(left, right, score, config, adjudicator)
        if verdict is DuplicateVerdict.UNIQUE:
            continue
        # A nota mais antiga do grupo permanece a original.
        duplicates[right.note_id] = DuplicateAssessment(
            note_id=right.note_id,
            verdict=verdict,
            duplicate_of=left.note_id if verdict is DuplicateVerdict.DUPLICATE else None,
            score=score,
            adjudicated=adjudicated,
            reason_codes=reason_codes,
        )

    assessments = tuple(
        NoteAssessment(
            note_id=note.note_id,
            duplicate=duplicates.get(
                note.note_id,
                DuplicateAssessment(
                    note_id=note.note_id,
                    verdict=DuplicateVerdict.UNIQUE,
                    score=0.0,
                    reason_codes=("no_candidate_above_threshold",),
                ),
            ),
            suggestions=(
                _note_type_suggestion(note, config),
                _priority_suggestion(note),
            ),
        )
        for note in batch.notes
    )
    return NoteBatchResult(
        batch_id=batch.batch_id,
        tenant_id=batch.tenant_id,
        as_of=batch.as_of,
        ruleset_version=RULESET_VERSION,
        config_hash=config_hash(config),
        adjudicator=getattr(adjudicator, "name", None) or "none",
        assessments=assessments,
    )


__all__ = ["RULESET_VERSION", "config_hash", "treat_notes"]
