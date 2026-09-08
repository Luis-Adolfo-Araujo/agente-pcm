"""Normalização e similaridade textual determinísticas para notas."""

from __future__ import annotations

import re
import unicodedata

_TRIGRAM_SIZE = 3
_NON_TEXT = re.compile(r"[^0-9a-z\s]+")
_WHITESPACE = re.compile(r"\s+")


def normalize_note_text(value: str) -> str:
    """Reduz o texto a minúsculas sem acento nem pontuação.

    A normalização precede qualquer comparação para que diferença de digitação
    não vire diferença de conteúdo.
    """

    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accent = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return _WHITESPACE.sub(" ", _NON_TEXT.sub(" ", without_accent)).strip()


def _trigrams(value: str) -> set[str]:
    normalized = normalize_note_text(value)
    if not normalized:
        return set()
    padded = f"  {normalized} "
    return {
        padded[index : index + _TRIGRAM_SIZE]
        for index in range(len(padded) - _TRIGRAM_SIZE + 1)
    }


def trigram_similarity(left: str, right: str) -> float:
    """Jaccard sobre trigramas; 0 quando qualquer lado é vazio."""

    left_trigrams = _trigrams(left)
    right_trigrams = _trigrams(right)
    if not left_trigrams or not right_trigrams:
        return 0.0
    intersection = len(left_trigrams & right_trigrams)
    union = len(left_trigrams | right_trigrams)
    return round(intersection / union, 6)


__all__ = ["normalize_note_text", "trigram_similarity"]
