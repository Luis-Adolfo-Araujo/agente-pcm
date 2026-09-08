from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app, reset_service

SNAPSHOT_SOURCE = Path("demo/snapshots/demo-planta-modelo.json")


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    shutil.copy(SNAPSHOT_SOURCE, snapshots / SNAPSHOT_SOURCE.name)
    monkeypatch.setenv("MAIA_PILOT_SNAPSHOT_DIR", str(snapshots))
    monkeypatch.setenv("MAIA_PILOT_RUN_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("MAIA_PILOT_DB", str(tmp_path / "pilot.sqlite3"))
    monkeypatch.delenv("MAIA_PILOT_PASSWORD", raising=False)
    monkeypatch.delenv("MAIA_PILOT_SHOW_RAW_WORKER_IDS", raising=False)
    reset_service()
    with TestClient(create_app()) as test_client:
        yield test_client
    reset_service()


def test_health_needs_no_credential(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_snapshots_expose_the_frozen_catalogue(client: TestClient) -> None:
    payload = client.get("/api/snapshots").json()

    assert len(payload) == 1
    assert payload[0]["quality"]["operation_count"] == 1200
    assert len(payload[0]["sha256"]) == 64


def test_a_run_starts_queued_and_reports_its_period(client: TestClient) -> None:
    snapshot_id = client.get("/api/snapshots").json()[0]["snapshot_id"]

    response = client.post(
        "/api/runs",
        json={
            "snapshot_id": snapshot_id,
            "period_start": "2026-08-18",
            "period_end": "2026-08-24",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    assert body["request"]["period"]["start"].startswith("2026-08-18")
    assert body["request"]["period"]["end"].startswith("2026-08-25")


def test_an_unknown_snapshot_is_a_404(client: TestClient) -> None:
    response = client.post(
        "/api/runs",
        json={
            "snapshot_id": "nao-existe",
            "period_start": "2026-08-18",
            "period_end": "2026-08-24",
        },
    )

    assert response.status_code == 404


def test_an_inverted_period_is_refused(client: TestClient) -> None:
    snapshot_id = client.get("/api/snapshots").json()[0]["snapshot_id"]

    response = client.post(
        "/api/runs",
        json={
            "snapshot_id": snapshot_id,
            "period_start": "2026-08-24",
            "period_end": "2026-08-18",
        },
    )

    assert response.status_code == 422


def test_artifacts_of_an_unfinished_run_answer_409(client: TestClient) -> None:
    snapshot_id = client.get("/api/snapshots").json()[0]["snapshot_id"]
    run_id = client.post(
        "/api/runs",
        json={
            "snapshot_id": snapshot_id,
            "period_start": "2026-08-18",
            "period_end": "2026-08-24",
        },
    ).json()["run_id"]

    assert client.get(f"/api/runs/{run_id}/schedule").status_code == 409


def test_an_unknown_run_is_a_404(client: TestClient) -> None:
    assert client.get("/api/runs/nao-existe").status_code == 404
    assert client.get("/api/runs/nao-existe/backlog").status_code == 404


def test_a_password_locks_every_route_but_health(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    shutil.copy(SNAPSHOT_SOURCE, snapshots / SNAPSHOT_SOURCE.name)
    monkeypatch.setenv("MAIA_PILOT_SNAPSHOT_DIR", str(snapshots))
    monkeypatch.setenv("MAIA_PILOT_RUN_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("MAIA_PILOT_DB", str(tmp_path / "pilot.sqlite3"))
    monkeypatch.setenv("MAIA_PILOT_PASSWORD", "segredo")
    reset_service()
    with TestClient(create_app()) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/snapshots").status_code == 401
        authorised = client.get("/api/snapshots", headers={"Authorization": "Bearer segredo"})
        assert authorised.status_code == 200
    reset_service()
