from __future__ import annotations

from domain.notes.text import normalize_note_text, trigram_similarity


def test_normalization_removes_accent_case_and_punctuation() -> None:
    assert normalize_note_text("Vazamento no REDUTOR!") == "vazamento no redutor"


def test_normalization_collapses_repeated_whitespace() -> None:
    assert normalize_note_text("  troca   de   rolamento ") == "troca de rolamento"


def test_normalization_of_empty_text_is_empty() -> None:
    assert normalize_note_text("   ") == ""


def test_identical_texts_are_fully_similar() -> None:
    assert trigram_similarity("troca de rolamento", "troca de rolamento") == 1.0


def test_accent_and_case_do_not_reduce_similarity() -> None:
    assert trigram_similarity("Manutenção na roda", "manutencao na roda") == 1.0


def test_unrelated_texts_are_dissimilar() -> None:
    assert trigram_similarity("troca de rolamento", "pintura do portao") < 0.2


def test_partial_overlap_lands_between_the_extremes() -> None:
    score = trigram_similarity("vazamento de oleo no redutor", "vazamento de oleo na bomba")

    assert 0.3 < score < 0.9


def test_similarity_is_symmetric() -> None:
    first = trigram_similarity("troca de rolamento", "troca do rolamento")
    second = trigram_similarity("troca do rolamento", "troca de rolamento")

    assert first == second


def test_empty_text_has_no_similarity() -> None:
    assert trigram_similarity("", "qualquer coisa") == 0.0
