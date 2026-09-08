from __future__ import annotations

from datetime import UTC, datetime, timedelta

from application.notes.triage import treat_notes
from domain.notes.config import NoteTriageConfig
from domain.notes.entities import (
    DuplicateVerdict,
    FieldPolicy,
    MaintenanceNote,
    NoteAssessment,
    NoteBatch,
    NoteBatchResult,
)

BASE = datetime(2026, 8, 1, 9, tzinfo=UTC)


def note(
    note_id: str,
    title: str,
    *,
    days: int = 0,
    asset_id: str | None = "asset-1",
) -> MaintenanceNote:
    return MaintenanceNote(
        note_id=note_id,
        tenant_id="planta-modelo",
        source="tractian",
        created_at=BASE + timedelta(days=days),
        title=title,
        asset_id=asset_id,
    )


def batch(*notes: MaintenanceNote) -> NoteBatch:
    return NoteBatch(
        batch_id="batch-1",
        tenant_id="planta-modelo",
        source="tractian",
        as_of=BASE + timedelta(days=40),
        notes=notes,
    )


class RecordingAdjudicator:
    """Adjudicador falso: registra o que recebeu e responde o combinado."""

    name = "stub-adjudicator"

    def __init__(self, verdict: bool) -> None:
        self.verdict = verdict
        self.seen: list[tuple[str, str]] = []

    def is_duplicate(self, left: MaintenanceNote, right: MaintenanceNote) -> bool:
        self.seen.append((left.note_id, right.note_id))
        return self.verdict


def _assessment(result: NoteBatchResult, note_id: str) -> NoteAssessment:
    return next(item for item in result.assessments if item.note_id == note_id)


def test_identical_notes_are_marked_duplicate_without_the_adjudicator() -> None:
    adjudicator = RecordingAdjudicator(verdict=True)

    result = treat_notes(
        batch(note("n-1", "vazamento no redutor"), note("n-2", "vazamento no redutor", days=1)),
        NoteTriageConfig(),
        adjudicator=adjudicator,
    )

    assert _assessment(result, "n-2").duplicate.verdict is DuplicateVerdict.DUPLICATE
    assert _assessment(result, "n-2").duplicate.duplicate_of == "n-1"
    assert adjudicator.seen == []


def test_unrelated_notes_are_unique_without_the_adjudicator() -> None:
    adjudicator = RecordingAdjudicator(verdict=True)

    result = treat_notes(
        batch(
            note("n-1", "vazamento no redutor", asset_id="asset-1"),
            note("n-2", "pintura do portao da portaria", asset_id="asset-2", days=1),
        ),
        NoteTriageConfig(),
        adjudicator=adjudicator,
    )

    assert _assessment(result, "n-2").duplicate.verdict is DuplicateVerdict.UNIQUE
    assert adjudicator.seen == []


def test_only_the_grey_band_reaches_the_adjudicator() -> None:
    adjudicator = RecordingAdjudicator(verdict=True)
    config = NoteTriageConfig(duplicate_threshold=0.99, review_threshold=0.10)

    result = treat_notes(
        batch(
            note("n-1", "vazamento de oleo no redutor"),
            note("n-2", "vazamento de oleo na bomba", days=2),
        ),
        config,
        adjudicator=adjudicator,
    )

    assert adjudicator.seen == [("n-1", "n-2")]
    assert _assessment(result, "n-2").duplicate.verdict is DuplicateVerdict.DUPLICATE
    assert _assessment(result, "n-2").duplicate.adjudicated is True


def test_the_adjudicator_can_clear_a_grey_band_pair() -> None:
    adjudicator = RecordingAdjudicator(verdict=False)
    config = NoteTriageConfig(duplicate_threshold=0.99, review_threshold=0.10)

    result = treat_notes(
        batch(
            note("n-1", "vazamento de oleo no redutor"),
            note("n-2", "vazamento de oleo na bomba", days=2),
        ),
        config,
        adjudicator=adjudicator,
    )

    assert _assessment(result, "n-2").duplicate.verdict is DuplicateVerdict.UNIQUE


def test_without_an_adjudicator_the_grey_band_goes_to_human_review() -> None:
    """Sem adjudicador o modo seguro devolve trabalho, nunca afirma unicidade."""

    config = NoteTriageConfig(duplicate_threshold=0.99, review_threshold=0.10)

    result = treat_notes(
        batch(
            note("n-1", "vazamento de oleo no redutor"),
            note("n-2", "vazamento de oleo na bomba", days=2),
        ),
        config,
        adjudicator=None,
    )

    duplicate = _assessment(result, "n-2").duplicate
    assert duplicate.verdict is DuplicateVerdict.NEEDS_REVIEW
    assert "adjudicator_unavailable" in duplicate.reason_codes


def test_an_adjudicator_failure_degrades_to_review_instead_of_propagating() -> None:
    class BrokenAdjudicator:
        name = "broken"

        def is_duplicate(self, left: MaintenanceNote, right: MaintenanceNote) -> bool:
            raise RuntimeError("modelo indisponível")

    config = NoteTriageConfig(duplicate_threshold=0.99, review_threshold=0.10)

    result = treat_notes(
        batch(
            note("n-1", "vazamento de oleo no redutor"),
            note("n-2", "vazamento de oleo na bomba", days=2),
        ),
        config,
        adjudicator=BrokenAdjudicator(),
    )

    assert _assessment(result, "n-2").duplicate.verdict is DuplicateVerdict.NEEDS_REVIEW


def test_the_first_note_of_a_group_stays_the_original() -> None:
    result = treat_notes(
        batch(
            note("n-1", "vazamento no redutor"),
            note("n-2", "vazamento no redutor", days=1),
            note("n-3", "vazamento no redutor", days=2),
        ),
        NoteTriageConfig(),
        adjudicator=None,
    )

    assert _assessment(result, "n-1").duplicate.verdict is DuplicateVerdict.UNIQUE
    assert _assessment(result, "n-2").duplicate.duplicate_of == "n-1"
    assert _assessment(result, "n-3").duplicate.duplicate_of == "n-1"


def test_every_note_receives_an_assessment() -> None:
    result = treat_notes(
        batch(note("n-1", "a"), note("n-2", "b", asset_id="asset-2")),
        NoteTriageConfig(),
        adjudicator=None,
    )

    assert {item.note_id for item in result.assessments} == {"n-1", "n-2"}


def test_the_result_records_what_produced_it() -> None:
    result = treat_notes(batch(note("n-1", "a")), NoteTriageConfig(), adjudicator=None)

    assert result.config_hash
    assert result.ruleset_version
    assert result.adjudicator == "none"


def test_note_type_is_omitted_with_a_reason_when_no_catalog_is_configured() -> None:
    result = treat_notes(batch(note("n-1", "a")), NoteTriageConfig(), adjudicator=None)

    suggestion = next(
        item for item in _assessment(result, "n-1").suggestions if item.field == "note_type"
    )
    assert suggestion.value is None
    assert "catalog_not_configured" in suggestion.reason_codes
    assert suggestion.policy is FieldPolicy.ADVISORY


def test_priority_is_omitted_when_the_source_carries_no_historical_linkage() -> None:
    result = treat_notes(batch(note("n-1", "a")), NoteTriageConfig(), adjudicator=None)

    suggestion = next(
        item for item in _assessment(result, "n-1").suggestions if item.field == "priority_level"
    )
    assert suggestion.value is None
    assert "no_historical_linkage" in suggestion.reason_codes


def test_a_priority_already_registered_is_reported_as_registered() -> None:
    registered = note("n-1", "a").model_copy(update={"priority_level": 2})

    result = treat_notes(batch(registered), NoteTriageConfig(), adjudicator=None)

    suggestion = next(
        item for item in _assessment(result, "n-1").suggestions if item.field == "priority_level"
    )
    assert suggestion.value == "2"
    assert suggestion.origin.value == "registered"
