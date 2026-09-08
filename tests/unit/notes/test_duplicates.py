from __future__ import annotations

from datetime import UTC, datetime, timedelta

from domain.notes.config import NoteTriageConfig
from domain.notes.duplicates import candidate_pairs, score_pair
from domain.notes.entities import MaintenanceNote

BASE = datetime(2026, 8, 1, 9, tzinfo=UTC)


def note(
    note_id: str,
    title: str,
    *,
    asset_id: str | None = "asset-1",
    days: int = 0,
    description: str = "",
) -> MaintenanceNote:
    return MaintenanceNote(
        note_id=note_id,
        tenant_id="planta-modelo",
        source="tractian",
        created_at=BASE + timedelta(days=days),
        title=title,
        description=description,
        asset_id=asset_id,
    )


def test_same_asset_inside_the_window_becomes_a_candidate_pair() -> None:
    notes = (
        note("n-1", "vazamento no redutor"),
        note("n-2", "vazamento no redutor", days=3),
    )

    pairs = candidate_pairs(notes, NoteTriageConfig())

    assert [(left.note_id, right.note_id) for left, right in pairs] == [("n-1", "n-2")]


def test_same_asset_outside_the_window_is_not_compared() -> None:
    notes = (
        note("n-1", "vazamento no redutor"),
        note("n-2", "vazamento no redutor", days=90),
    )

    assert candidate_pairs(notes, NoteTriageConfig(window_days=30)) == ()


def test_different_assets_do_not_pair_when_the_text_is_unrelated() -> None:
    notes = (
        note("n-1", "vazamento no redutor", asset_id="asset-1"),
        note("n-2", "pintura do portao", asset_id="asset-2"),
    )

    assert candidate_pairs(notes, NoteTriageConfig()) == ()


def test_notes_without_asset_still_pair_through_text_similarity() -> None:
    notes = (
        note("n-1", "troca de rolamento do motor", asset_id=None),
        note("n-2", "troca de rolamento do motor", asset_id=None, days=1),
    )

    pairs = candidate_pairs(notes, NoteTriageConfig())

    assert [(left.note_id, right.note_id) for left, right in pairs] == [("n-1", "n-2")]


def test_every_pair_appears_once_and_in_stable_order() -> None:
    notes = (
        note("n-3", "vazamento no redutor", days=2),
        note("n-1", "vazamento no redutor"),
        note("n-2", "vazamento no redutor", days=1),
    )

    pairs = candidate_pairs(notes, NoteTriageConfig())

    assert [(left.note_id, right.note_id) for left, right in pairs] == [
        ("n-1", "n-2"),
        ("n-1", "n-3"),
        ("n-2", "n-3"),
    ]


def test_identical_note_on_the_same_asset_scores_at_the_top() -> None:
    score = score_pair(
        note("n-1", "vazamento no redutor"),
        note("n-2", "vazamento no redutor", days=1),
        NoteTriageConfig(),
    )

    assert score > 0.9


def test_same_text_on_a_different_asset_scores_lower_than_same_asset() -> None:
    config = NoteTriageConfig()
    same_asset = score_pair(
        note("n-1", "vazamento no redutor"),
        note("n-2", "vazamento no redutor", days=1),
        config,
    )
    other_asset = score_pair(
        note("n-1", "vazamento no redutor"),
        note("n-2", "vazamento no redutor", asset_id="asset-9", days=1),
        config,
    )

    assert other_asset < same_asset


def test_distance_in_time_reduces_the_score() -> None:
    config = NoteTriageConfig()
    near = score_pair(note("n-1", "vazamento"), note("n-2", "vazamento", days=1), config)
    far = score_pair(note("n-1", "vazamento"), note("n-2", "vazamento", days=25), config)

    assert far < near


def test_unknown_asset_is_neutral_not_evidence_against_duplication() -> None:
    """Ativo ausente é "não sei", nunca "são ativos diferentes"."""

    config = NoteTriageConfig()
    both_unknown = score_pair(
        note("n-1", "fabricacao de carro para amostras", asset_id=None),
        note("n-2", "fabricacao de carro para amostras", asset_id=None, days=13),
        config,
    )
    known_different = score_pair(
        note("n-1", "fabricacao de carro para amostras", asset_id="asset-1"),
        note("n-2", "fabricacao de carro para amostras", asset_id="asset-2", days=13),
        config,
    )

    assert both_unknown > known_different


def test_identical_text_with_unknown_asset_reaches_the_duplicate_threshold() -> None:
    config = NoteTriageConfig()

    score = score_pair(
        note("n-1", "fabricacao de carro para amostras", asset_id=None),
        note("n-2", "fabricacao de carro para amostras", asset_id=None, days=13),
        config,
    )

    assert score >= config.duplicate_threshold


def test_identical_text_on_proven_different_assets_stays_in_the_grey_band() -> None:
    """Duas rodas distintas com o mesmo defeito não são a mesma nota."""

    config = NoteTriageConfig()

    score = score_pair(
        note("n-1", "manutencao na roda de apoio", asset_id="asset-1"),
        note("n-2", "manutencao na roda de apoio", asset_id="asset-2"),
        config,
    )

    assert config.review_threshold <= score < config.duplicate_threshold


def test_one_sided_unknown_asset_is_also_neutral() -> None:
    config = NoteTriageConfig()
    one_unknown = score_pair(
        note("n-1", "troca de rolamento", asset_id="asset-1"),
        note("n-2", "troca de rolamento", asset_id=None),
        config,
    )
    known_different = score_pair(
        note("n-1", "troca de rolamento", asset_id="asset-1"),
        note("n-2", "troca de rolamento", asset_id="asset-2"),
        config,
    )

    assert one_unknown > known_different
