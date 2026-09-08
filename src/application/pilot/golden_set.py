"""Exportação do feedback humano no formato do golden set da Fase 5.

O arquivo alimenta a avaliação offline das skills. Ele carrega apenas a chave da
recomendação e o veredito; a identidade de quem avaliou fica no banco do piloto e
não é propagada para o conjunto de dados.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from application.pilot.models import FeedbackRecord

SCHEMA_VERSION = "1.0"


def _entry(record: FeedbackRecord) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": record.snapshot_id,
        "run_id": record.run_id,
        "operation_id": record.operation_id,
        "skill": record.skill.value,
        "verdict": record.verdict.value,
        "reason": record.reason,
        "recorded_at": record.recorded_at.isoformat(),
    }


def golden_set_jsonl(records: Iterable[FeedbackRecord]) -> str:
    """Serializa as avaliações em JSONL estável e independente da ordem recebida."""

    entries = sorted(
        (_entry(record) for record in records),
        key=lambda entry: (
            str(entry["snapshot_id"]),
            str(entry["operation_id"]),
            str(entry["skill"]),
            str(entry["recorded_at"]),
        ),
    )
    if not entries:
        return ""
    lines = [
        json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for entry in entries
    ]
    return "\n".join(lines) + "\n"


__all__ = ["SCHEMA_VERSION", "golden_set_jsonl"]
