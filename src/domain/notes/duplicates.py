"""Bloqueio e pontuação determinísticos de pares de notas.

O bloqueio existe para que o custo não cresça com o quadrado do lote: só pares
plausíveis chegam à pontuação, e só a faixa cinzenta chega ao adjudicador.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import combinations

from domain.notes.config import NoteTriageConfig
from domain.notes.entities import MaintenanceNote
from domain.notes.text import trigram_similarity

_SECONDS_PER_DAY = 24 * 60 * 60

NotePair = tuple[MaintenanceNote, MaintenanceNote]


def _days_apart(left: MaintenanceNote, right: MaintenanceNote) -> float:
    return abs((left.created_at - right.created_at).total_seconds()) / _SECONDS_PER_DAY


def _ordered(left: MaintenanceNote, right: MaintenanceNote) -> NotePair:
    return (left, right) if left.note_id <= right.note_id else (right, left)


def candidate_pairs(
    notes: Sequence[MaintenanceNote],
    config: NoteTriageConfig,
) -> tuple[NotePair, ...]:
    """Gera os pares que valem comparação, em ordem estável."""

    pairs: list[NotePair] = []
    for left, right in combinations(sorted(notes, key=lambda item: item.note_id), 2):
        if _days_apart(left, right) > config.window_days:
            continue
        same_asset = (
            left.asset_id is not None and left.asset_id == right.asset_id
        )
        if same_asset:
            pairs.append(_ordered(left, right))
            continue
        similarity = trigram_similarity(left.comparable_text, right.comparable_text)
        if similarity >= config.blocking_similarity:
            pairs.append(_ordered(left, right))
    return tuple(pairs)


def score_pair(
    left: MaintenanceNote,
    right: MaintenanceNote,
    config: NoteTriageConfig,
) -> float:
    """Combina semelhança textual, coincidência de ativo e proximidade temporal."""

    text = trigram_similarity(left.comparable_text, right.comparable_text)
    recency = max(0.0, 1.0 - _days_apart(left, right) / config.window_days)
    weighted = text * config.text_weight + recency * config.recency_weight
    total_weight = config.text_weight + config.recency_weight

    # Ativo desconhecido em qualquer lado é ausência de informação, não prova de
    # que os ativos diferem: a parcela sai do cálculo em vez de pontuar zero.
    if left.asset_id is not None and right.asset_id is not None:
        weighted += (1.0 if left.asset_id == right.asset_id else 0.0) * config.asset_weight
        total_weight += config.asset_weight

    if total_weight <= 0:
        return 0.0
    return round(weighted / total_weight, 6)


__all__ = ["NotePair", "candidate_pairs", "score_pair"]
