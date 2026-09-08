"""Fronteira do julgamento por modelo sobre pares de notas."""

from __future__ import annotations

from typing import Protocol

from domain.notes.entities import MaintenanceNote


class DuplicateAdjudicator(Protocol):
    """Julga um par que o score determinístico não resolveu.

    Recebe apenas os dois textos, datas e ativo. Não vê o lote, não ordena, não
    decide prioridade, e o resultado nunca preenche campo canônico.
    """

    name: str

    def is_duplicate(self, left: MaintenanceNote, right: MaintenanceNote) -> bool: ...


__all__ = ["DuplicateAdjudicator"]
