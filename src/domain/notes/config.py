"""Configuração versionável do tratamento de notas."""

from __future__ import annotations

from pydantic import Field

from domain.notes.entities import ContractModel


class NoteTriageConfig(ContractModel):
    # Bloqueio: só compara notas do mesmo ativo dentro da janela, ou pares cujo
    # texto já é parecido o bastante para valer a comparação.
    window_days: int = Field(default=30, gt=0)
    blocking_similarity: float = Field(default=0.55, ge=0, le=1)
    # Faixas do veredito. O default é conservador: faixa cinzenta larga, porque
    # encaminhar para revisão custa menos que afirmar unicidade errada.
    duplicate_threshold: float = Field(default=0.88, ge=0, le=1)
    review_threshold: float = Field(default=0.55, ge=0, le=1)
    # Pesos do score determinístico do par.
    text_weight: float = Field(default=0.70, ge=0)
    asset_weight: float = Field(default=0.20, ge=0)
    recency_weight: float = Field(default=0.10, ge=0)
    # Catálogo fechado de tipos de nota. Vazio desativa a sugestão de tipo.
    note_type_catalog: tuple[str, ...] = ()

    def model_post_init(self, __context: object) -> None:
        if self.review_threshold > self.duplicate_threshold:
            raise ValueError("review_threshold must not exceed duplicate_threshold")


__all__ = ["NoteTriageConfig"]
