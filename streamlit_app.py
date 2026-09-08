"""Entrada da demonstração pública: o piloto sobre o mundo fictício.

O Streamlit Community Cloud procura este arquivo na raiz do repositório. Ele
só resolve caminhos e aponta o catálogo para `demo/snapshots`, onde mora o
snapshot gerado por semente. A interface e a camada de serviço são as mesmas do
piloto interno; nada aqui é uma versão paralela do produto.

O acesso é anônimo de propósito: a demonstração existe para que qualquer pessoa
gere uma programação. Como o dado é fictício, não há o que proteger com senha.
Sobre dado real, `MAIA_PILOT_PASSWORD` continua obrigatória.

O Streamlit serve `static/` a partir da pasta do arquivo de entrada, e o tema
pede as fontes em `app/static/fonts`. Cada entrada precisa da própria pasta:
link simbólico recebe 400, e a cópia só valeria depois que o servidor já subiu.
Por isso `static/fonts` na raiz repete os arquivos de `src/presentation/static/
fonts`, e um teste falha se as duas pastas divergirem.
"""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

DEFAULTS = {
    "MAIA_PILOT_SNAPSHOT_DIR": str(ROOT / "demo" / "snapshots"),
    "MAIA_PILOT_RUN_DIR": str(ROOT / "var" / "demo" / "runs"),
    "MAIA_PILOT_DB": str(ROOT / "var" / "demo" / "demo.sqlite3"),
    "MAIA_PILOT_TENANT_LABEL": "Planta Modelo (dado fictício)",
    "MAIA_PILOT_USER": "visitante",
    "MAIA_PILOT_ALLOW_ANONYMOUS": "true",
    # Os técnicos são fictícios: o pseudônimo esconderia um dado que não
    # existe e tornaria a tela mais difícil de ler.
    "MAIA_PILOT_SHOW_RAW_WORKER_IDS": "true",
}
for key, value in DEFAULTS.items():
    os.environ.setdefault(key, value)

Path(os.environ["MAIA_PILOT_RUN_DIR"]).mkdir(parents=True, exist_ok=True)

runpy.run_path(str(SOURCE / "presentation" / "pilot_app.py"), run_name="__main__")
