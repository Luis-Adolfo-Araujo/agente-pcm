"""Fixtures compartilhadas pelos testes de integração do piloto."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from application.pilot.service import PilotService
from tests.support.planning import request_base, snapshot_base


class _ImmediateExecutor:
    """Executa a tarefa na hora, sem thread — a run já sai `COMPLETED` de `start_run`."""

    def submit(self, run_id: str, task: Callable[[], None]) -> None:
        task()


@pytest.fixture()
def service_com_run(tmp_path: Path) -> tuple[PilotService, str]:
    """Serviço com um snapshot congelado e uma run já completa, prontos para ajustes."""

    snapshot = snapshot_base()
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    (snapshot_dir / f"{snapshot.snapshot_id}.json").write_text(
        snapshot.model_dump_json(indent=2),
        encoding="utf-8",
    )
    service = PilotService(
        snapshot_dir=snapshot_dir,
        run_dir=tmp_path / "runs",
        db_path=tmp_path / "pilot.sqlite3",
        executor=_ImmediateExecutor(),
    )
    run = service.start_run(snapshot_id=snapshot.snapshot_id, request=request_base())
    return service, run.run_id
