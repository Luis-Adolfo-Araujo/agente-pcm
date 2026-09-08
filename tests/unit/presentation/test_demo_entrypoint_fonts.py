"""A entrada da demonstração precisa das mesmas fontes que o piloto interno.

O Streamlit resolve `static/` pela pasta do arquivo de entrada, então a raiz
carrega uma cópia das fontes da apresentação. Cópia sem guarda vira divergência
silenciosa: o piloto ganha uma fonte nova e a demonstração continua com a
antiga. Este teste é a guarda.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CANONICAL = ROOT / "src" / "presentation" / "static" / "fonts"
MIRROR = ROOT / "static" / "fonts"


def _digests(folder: Path) -> dict[str, str]:
    return {
        item.name: hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(folder.glob("*.woff2"))
    }


def test_the_demo_entrypoint_serves_the_same_fonts() -> None:
    canonical = _digests(CANONICAL)

    assert canonical, "a apresentação precisa declarar suas fontes"
    assert _digests(MIRROR) == canonical
