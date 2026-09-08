from __future__ import annotations

from datetime import UTC, datetime

from infrastructure.database.tractian.mapper import MappingReport
from infrastructure.database.tractian.notes_mapper import map_notes

CREATED = datetime(2026, 8, 1, 9, tzinfo=UTC)


def row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "note_id": "req-1",
        "created_at": CREATED,
        "title": "Vazamento no redutor",
        "description": "Observado vazamento constante",
        "asset_id": "asset-1",
        "status": "approved",
        "number": 42,
    }
    base.update(overrides)
    return base


def test_maps_a_work_request_into_a_canonical_note() -> None:
    report = MappingReport()

    notes = map_notes([row()], tenant_id="planta-modelo", report=report)

    assert len(notes) == 1
    note = notes[0]
    assert note.note_id == "req-1"
    assert note.tenant_id == "planta-modelo"
    assert note.source == "tractian"
    assert note.title == "Vazamento no redutor"
    assert note.asset_id == "asset-1"


def test_preserves_the_source_number_for_the_output_file() -> None:
    notes = map_notes([row()], tenant_id="planta-modelo", report=MappingReport())

    assert notes[0].source_fields["number"] == "42"


def test_tractian_requests_carry_no_note_type_or_priority() -> None:
    """A fonte não tem esses campos; inventá-los seria mentir sobre o cadastro."""

    notes = map_notes([row()], tenant_id="planta-modelo", report=MappingReport())

    assert notes[0].note_type is None
    assert notes[0].priority_level is None


def test_a_note_without_asset_is_still_mapped() -> None:
    notes = map_notes([row(asset_id=None)], tenant_id="planta-modelo", report=MappingReport())

    assert notes[0].asset_id is None


def test_an_invalid_row_is_counted_instead_of_aborting_the_batch() -> None:
    report = MappingReport()

    notes = map_notes(
        [row(), row(note_id="", number=7)],
        tenant_id="planta-modelo",
        report=report,
    )

    assert len(notes) == 1
    assert report.as_metadata()["rejected_records"] == 1
    assert report.rejected_by_domain == {"work_requests": 1}


def test_a_naive_timestamp_is_rejected_not_silently_assumed() -> None:
    report = MappingReport()

    notes = map_notes(
        [row(created_at=datetime(2026, 8, 1, 9))],
        tenant_id="planta-modelo",
        report=report,
    )

    assert notes == ()
    assert report.as_metadata()["rejected_records"] == 1
