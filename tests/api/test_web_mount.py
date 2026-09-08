"""A API pode servir a interface exportada no mesmo endereço.

Publicar a demonstração em dois hosts obrigaria a abrir CORS e a manter duas
URLs vivas. Com a interface montada ao lado da API, o navegador faz tudo na
mesma origem — e o `/api` continua sendo da API, não do arquivo estático.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app, reset_service


@pytest.fixture()
def site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    root = tmp_path / "site"
    (root / "_next").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>MAIA</title>", encoding="utf-8")
    (root / "_next" / "app.js").write_text("console.log('maia')", encoding="utf-8")
    monkeypatch.setenv("MAIA_WEB_DIR", str(root))
    monkeypatch.setenv("MAIA_PILOT_SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    monkeypatch.setenv("MAIA_PILOT_RUN_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("MAIA_PILOT_DB", str(tmp_path / "pilot.sqlite3"))
    reset_service()
    yield root
    reset_service()


def test_the_root_serves_the_exported_interface(site: Path) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "<title>MAIA</title>" in response.text


def test_the_bundle_is_reachable(site: Path) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/_next/app.js")

    assert response.status_code == 200
    assert "maia" in response.text


def test_the_api_still_wins_over_the_static_site(site: Path) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/health")

    assert response.json() == {"status": "ok"}


def test_without_the_variable_nothing_is_mounted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MAIA_WEB_DIR", raising=False)
    monkeypatch.setenv("MAIA_PILOT_SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    monkeypatch.setenv("MAIA_PILOT_RUN_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("MAIA_PILOT_DB", str(tmp_path / "pilot.sqlite3"))
    reset_service()

    with TestClient(create_app()) as client:
        response = client.get("/")

    reset_service()
    assert response.status_code == 404


def test_a_missing_directory_is_not_mounted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Apontar para uma pasta que não existe é erro de configuração, não 500."""

    monkeypatch.setenv("MAIA_WEB_DIR", str(tmp_path / "ausente"))
    monkeypatch.setenv("MAIA_PILOT_SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    monkeypatch.setenv("MAIA_PILOT_RUN_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("MAIA_PILOT_DB", str(tmp_path / "pilot.sqlite3"))
    reset_service()

    with TestClient(create_app()) as client:
        response = client.get("/")

    reset_service()
    assert response.status_code == 404
