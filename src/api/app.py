"""API HTTP do piloto.

Uma casca fina sobre ``PilotService``: nenhuma regra vive aqui. A pseudonimização
acontece na saída, para que o identificador de origem não deixe o processo sem
autorização explícita.
"""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, cast

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from application.config import load_planning_config
from application.pilot.models import ExportFormat, FeedbackInput
from application.pilot.service import PilotService
from domain.planning.config import PlanningConfig
from domain.planning.entities import PlanningRequest, TimeWindow
from domain.planning.enums import DecisionType
from presentation.privacy import (
    password_is_valid,
    pseudonymize_worker_fields,
    raw_worker_ids_enabled,
)

DEFAULT_SNAPSHOT_DIR = "var/pilot/snapshots"
DEFAULT_RUN_DIR = "var/pilot/runs"
DEFAULT_DB_PATH = "var/pilot/pilot.sqlite3"

_service: PilotService | None = None


def get_service() -> PilotService:
    global _service
    if _service is None:
        _service = PilotService(
            snapshot_dir=Path(os.environ.get("MAIA_PILOT_SNAPSHOT_DIR", DEFAULT_SNAPSHOT_DIR)),
            run_dir=Path(os.environ.get("MAIA_PILOT_RUN_DIR", DEFAULT_RUN_DIR)),
            db_path=Path(os.environ.get("MAIA_PILOT_DB", DEFAULT_DB_PATH)),
        )
    return _service


def reset_service() -> None:
    """Descarta o serviço em memória. Usado pelos testes."""

    global _service
    _service = None


def require_access(request: Request) -> None:
    """Senha única do ambiente interno, enviada como Bearer."""

    expected = os.environ.get("MAIA_PILOT_PASSWORD")
    if not expected:
        return
    header = request.headers.get("authorization", "")
    supplied = header[7:] if header.lower().startswith("bearer ") else ""
    if not password_is_valid(expected, supplied):
        raise HTTPException(status_code=401, detail="credencial inválida")


def _clean(payload: Any) -> dict[str, Any]:
    """Troca identificadores de pessoa por alias antes de a resposta sair."""

    sanitized = pseudonymize_worker_fields(payload, reveal=raw_worker_ids_enabled(os.environ))
    return cast("dict[str, Any]", sanitized)


class StartRunBody(BaseModel):
    snapshot_id: str = Field(min_length=1)
    period_start: date
    period_end: date
    config: dict[str, Any] | None = None


class DecisionBody(BaseModel):
    decision: str
    decided_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class FeedbackItemBody(BaseModel):
    operation_id: str
    skill: str
    verdict: str
    reason: str


class FeedbackBody(BaseModel):
    recorded_by: str = Field(min_length=1)
    items: list[FeedbackItemBody]


def _mount_web(app: FastAPI) -> None:
    """Monta a interface exportada na raiz, quando houver uma para montar.

    Publicar em dois hosts custaria CORS aberto e duas URLs vivas. Com a
    interface no mesmo endereço da API, o navegador não sai da origem. A
    montagem vem depois das rotas, então `/api` continua sendo da API.

    Sem a variável, ou apontando para pasta inexistente, nada é montado: a
    API sobe do mesmo jeito para quem só quer o backend.
    """

    raw = os.environ.get("MAIA_WEB_DIR", "").strip()
    if not raw:
        return
    directory = Path(raw)
    if not directory.is_dir():
        return
    app.mount("/", StaticFiles(directory=directory, html=True), name="web")


def create_app() -> FastAPI:
    app = FastAPI(title="MAIA · piloto de PCM", version="1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("MAIA_PILOT_ORIGINS", "http://localhost:3001").split(","),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/snapshots", dependencies=[Depends(require_access)])
    def snapshots(service: PilotService = Depends(get_service)) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in service.list_snapshots()]

    @app.get("/api/runs", dependencies=[Depends(require_access)])
    def runs(service: PilotService = Depends(get_service)) -> list[dict[str, Any]]:
        return [_clean(item.model_dump(mode="json")) for item in service.list_runs()]

    @app.post("/api/runs", dependencies=[Depends(require_access)], status_code=201)
    def start_run(
        body: StartRunBody,
        service: PilotService = Depends(get_service),
    ) -> dict[str, Any]:
        try:
            snapshot = next(
                item for item in service.list_snapshots() if item.snapshot_id == body.snapshot_id
            )
        except StopIteration:
            raise HTTPException(status_code=404, detail="recorte não encontrado") from None
        if body.period_end < body.period_start:
            raise HTTPException(status_code=422, detail="período invertido")
        tzinfo = snapshot.as_of.tzinfo
        request = PlanningRequest(
            tenant_id=snapshot.tenant_id,
            period=TimeWindow(
                start=datetime.combine(body.period_start, time.min, tzinfo=tzinfo),
                end=datetime.combine(body.period_end + timedelta(days=1), time.min, tzinfo=tzinfo),
            ),
            as_of=snapshot.as_of,
            dry_run=True,
        )
        config = (
            PlanningConfig.model_validate(body.config)
            if body.config
            else load_planning_config(Path("config/tenants/planta-modelo.yaml"))
        )
        run = service.start_run(
            snapshot_id=body.snapshot_id,
            request=request,
            config=config,
        )
        return _clean(run.model_dump(mode="json"))

    def _run_or_404(service: PilotService, run_id: str) -> Any:
        try:
            return service.get_run(run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="execução não encontrada") from None

    @app.get("/api/runs/{run_id}", dependencies=[Depends(require_access)])
    def run_detail(
        run_id: str,
        service: PilotService = Depends(get_service),
    ) -> dict[str, Any]:
        return _clean(_run_or_404(service, run_id).model_dump(mode="json"))

    def _artifact(service: PilotService, run_id: str, reader: str) -> dict[str, Any]:
        _run_or_404(service, run_id)
        try:
            return _clean(getattr(service, reader)(run_id))
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None

    @app.get("/api/runs/{run_id}/backlog", dependencies=[Depends(require_access)])
    def backlog(run_id: str, service: PilotService = Depends(get_service)) -> dict[str, Any]:
        return _artifact(service, run_id, "get_backlog")

    @app.get("/api/runs/{run_id}/schedule", dependencies=[Depends(require_access)])
    def schedule(run_id: str, service: PilotService = Depends(get_service)) -> dict[str, Any]:
        return _artifact(service, run_id, "get_schedule")

    @app.get("/api/runs/{run_id}/verification", dependencies=[Depends(require_access)])
    def verification(run_id: str, service: PilotService = Depends(get_service)) -> dict[str, Any]:
        return _artifact(service, run_id, "get_verification")

    @app.post("/api/runs/{run_id}/decision", dependencies=[Depends(require_access)])
    def decide(
        run_id: str,
        body: DecisionBody,
        service: PilotService = Depends(get_service),
    ) -> dict[str, Any]:
        _run_or_404(service, run_id)
        try:
            run = service.record_decision(
                run_id=run_id,
                decision=DecisionType(body.decision),
                decided_by=body.decided_by,
                reason=body.reason,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        return _clean(run.model_dump(mode="json"))

    @app.post("/api/runs/{run_id}/feedback", dependencies=[Depends(require_access)])
    def feedback(
        run_id: str,
        body: FeedbackBody,
        service: PilotService = Depends(get_service),
    ) -> list[dict[str, Any]]:
        _run_or_404(service, run_id)
        try:
            records = service.record_feedback(
                run_id=run_id,
                items=[
                    FeedbackInput(
                        operation_id=item.operation_id,
                        skill=item.skill,
                        verdict=item.verdict,
                        reason=item.reason,
                    )
                    for item in body.items
                ],
                recorded_by=body.recorded_by,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        return [record.model_dump(mode="json") for record in records]

    @app.get("/api/runs/{run_id}/export", dependencies=[Depends(require_access)])
    def export(
        run_id: str,
        format: str = Query(default="json"),
        service: PilotService = Depends(get_service),
    ) -> dict[str, Any]:
        _run_or_404(service, run_id)
        try:
            bundle = service.export_run(run_id=run_id, format=ExportFormat(format))
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        return {"run_id": bundle.run_id, "format": bundle.format.value, "files": bundle.files}

    _mount_web(app)
    return app


app = create_app()

__all__ = ["app", "create_app", "get_service", "reset_service", "require_access"]
