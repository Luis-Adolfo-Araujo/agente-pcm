"""Congela uma rodada do agente como arquivo estático para a interface.

A demonstração pública não tem servidor: a página é olhada e ajustada, não
serve para provar a API. Então a rodada acontece aqui, uma vez, pelo agente de
verdade sobre a planta fictícia, e as respostas viram JSON ao lado da página.

Os arquivos saem do próprio cliente HTTP da API, não de um molde escrito à mão.
Assim o que a interface lê na demonstração tem exatamente a forma que ela
receberia de um servidor — se o contrato mudar, é aqui que aparece.

    uv run python scripts/gerar_artefatos_demo.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "web" / "public" / "demo-api"
PERIODO = ("2026-08-24", "2026-08-30")


def main() -> int:
    sys.path.insert(0, str(RAIZ / "src"))
    os.environ.setdefault("MAIA_PILOT_SNAPSHOT_DIR", str(RAIZ / "demo" / "snapshots"))
    os.environ.setdefault("MAIA_PILOT_RUN_DIR", str(RAIZ / "var" / "artefatos" / "runs"))
    os.environ.setdefault("MAIA_PILOT_DB", str(RAIZ / "var" / "artefatos" / "demo.sqlite3"))
    # Os técnicos são fictícios: o pseudônimo esconderia um dado que não existe.
    os.environ.setdefault("MAIA_PILOT_SHOW_RAW_WORKER_IDS", "true")

    from fastapi.testclient import TestClient

    from api.app import create_app

    DESTINO.mkdir(parents=True, exist_ok=True)

    with TestClient(create_app()) as cliente:
        snapshots = cliente.get("/api/snapshots").json()
        if not snapshots:
            raise SystemExit("nenhum snapshot no catálogo; gere o da demonstração antes")
        _escrever("snapshots", snapshots)

        criada = cliente.post(
            "/api/runs",
            json={
                "snapshot_id": snapshots[0]["snapshot_id"],
                "period_start": PERIODO[0],
                "period_end": PERIODO[1],
            },
        ).json()
        run_id = criada["run_id"]

        run = criada
        for _ in range(240):
            run = cliente.get(f"/api/runs/{run_id}").json()
            if run["status"] in ("completed", "failed"):
                break
            time.sleep(0.5)
        if run["status"] != "completed":
            raise SystemExit(f"a rodada terminou como {run['status']}")

        _escrever("run", run)
        _escrever("runs", [run])
        for nome in ("backlog", "schedule", "verification"):
            _escrever(nome, cliente.get(f"/api/runs/{run_id}/{nome}").json())

    for arquivo in sorted(DESTINO.iterdir()):
        print(f"{arquivo.name}: {arquivo.stat().st_size / 1_000_000:.2f} MB")
    return 0


def _escrever(nome: str, conteudo: object) -> None:
    """Sem indentação: o arquivo é para o navegador, e o repositório sente o peso."""

    caminho = DESTINO / f"{nome}.json"
    caminho.write_text(json.dumps(conteudo, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
