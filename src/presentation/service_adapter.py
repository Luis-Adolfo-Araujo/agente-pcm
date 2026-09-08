"""Adapter fino entre Streamlit e ``application.pilot.service.PilotService``."""

from __future__ import annotations

import importlib
import inspect
import os
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from domain.planning.config import PlanningConfig
from domain.planning.entities import PlanningRequest
from presentation.view_models import to_plain

DEFAULT_SNAPSHOT_DIR = "var/pilot/snapshots"
DEFAULT_RUN_DIR = "var/pilot/runs"
DEFAULT_DB_PATH = "var/pilot/pilot.sqlite3"


@runtime_checkable
class PilotServiceProtocol(Protocol):
    """Superfície esperada pela apresentação; modelos concretos ficam no app."""

    def list_snapshots(self) -> Sequence[Any]: ...

    def start_run(
        self,
        *,
        snapshot_id: str,
        request: PlanningRequest,
        config: PlanningConfig | None = None,
    ) -> Any: ...

    def get_run(self, run_id: str) -> Any: ...

    def get_backlog(self, run_id: str) -> Any: ...

    def get_schedule(self, run_id: str) -> Any: ...

    def get_verification(self, run_id: str) -> Any: ...

    def record_decision(
        self,
        *,
        run_id: str,
        decision: Any,
        decided_by: str,
        reason: str,
        decided_at: datetime | None = None,
    ) -> Any: ...

    def record_feedback(
        self,
        *,
        run_id: str,
        items: Sequence[Any],
        recorded_by: str,
        recorded_at: datetime | None = None,
    ) -> Sequence[Any]: ...

    def export_run(self, *, run_id: str, format: Any) -> Any: ...


def _pilot_symbol(name: str) -> Any:
    for module_name in ("application.pilot.models", "application.pilot.service"):
        module = importlib.import_module(module_name)
        if hasattr(module, name):
            return getattr(module, name)
    raise RuntimeError(f"application pilot does not expose {name}")


def _enum_value(name: str, value: str) -> Any:
    enum_type = _pilot_symbol(name)
    try:
        return enum_type(value)
    except ValueError:
        return enum_type[value.upper()]


def _feedback_input(item: Mapping[str, Any]) -> Any:
    model = _pilot_symbol("FeedbackInput")
    if hasattr(model, "model_validate"):
        return model.model_validate(dict(item))
    return model(**dict(item))


class PilotServiceAdapter:
    """Mantém detalhes dos modelos de persistência fora das telas."""

    def __init__(self, service: PilotServiceProtocol) -> None:
        self._service = service

    def list_snapshots(self) -> Sequence[Any]:
        return self._service.list_snapshots()

    def start_run(
        self,
        *,
        snapshot_id: str,
        request: PlanningRequest,
        config: PlanningConfig,
    ) -> Any:
        return self._service.start_run(
            snapshot_id=snapshot_id,
            request=request,
            config=config,
        )

    def get_run(self, run_id: str) -> Any:
        return self._service.get_run(run_id)

    def list_runs(self) -> Sequence[Any]:
        method = getattr(self._service, "list_runs", None)
        if callable(method):
            result = method()
            return result if isinstance(result, Sequence) else ()
        return ()

    def get_backlog(self, run_id: str) -> Any:
        return self._service.get_backlog(run_id)

    def get_schedule(self, run_id: str) -> Any:
        return self._service.get_schedule(run_id)

    def get_verification(self, run_id: str) -> Any:
        return self._service.get_verification(run_id)

    def record_decision(
        self,
        *,
        run_id: str,
        decision: str,
        decided_by: str,
        reason: str,
    ) -> Any:
        return self._service.record_decision(
            run_id=run_id,
            decision=_enum_value("DecisionType", decision),
            decided_by=decided_by,
            reason=reason,
        )

    def record_feedback(
        self,
        *,
        run_id: str,
        items: Sequence[Mapping[str, Any]],
        recorded_by: str,
    ) -> Sequence[Any]:
        typed_items = tuple(_feedback_input(item) for item in items)
        return self._service.record_feedback(
            run_id=run_id,
            items=typed_items,
            recorded_by=recorded_by,
        )

    def export_files(self, *, run_id: str, export_format: str) -> dict[str, bytes]:
        try:
            typed_format = _enum_value("ExportFormat", export_format)
        except (KeyError, RuntimeError, ValueError):
            typed_format = export_format
        bundle = to_plain(self._service.export_run(run_id=run_id, format=typed_format))
        if not isinstance(bundle, dict) or not isinstance(bundle.get("files"), dict):
            raise RuntimeError("pilot export did not return an ExportBundle with files")
        return {
            str(filename): (
                content if isinstance(content, bytes) else str(content).encode("utf-8")
            )
            for filename, content in bundle["files"].items()
        }


def _constructor_kwargs(service_type: type[Any], environment: Mapping[str, str]) -> dict[str, Any]:
    signature = inspect.signature(service_type)
    available = {
        "snapshot_dir": Path(environment.get("MAIA_PILOT_SNAPSHOT_DIR", DEFAULT_SNAPSHOT_DIR)),
        "snapshot_directory": Path(
            environment.get("MAIA_PILOT_SNAPSHOT_DIR", DEFAULT_SNAPSHOT_DIR)
        ),
        "run_dir": Path(environment.get("MAIA_PILOT_RUN_DIR", DEFAULT_RUN_DIR)),
        "run_directory": Path(environment.get("MAIA_PILOT_RUN_DIR", DEFAULT_RUN_DIR)),
        "db_path": Path(environment.get("MAIA_PILOT_DB", DEFAULT_DB_PATH)),
        "database_path": Path(environment.get("MAIA_PILOT_DB", DEFAULT_DB_PATH)),
    }
    return {
        name: available[name]
        for name, parameter in signature.parameters.items()
        if name in available
        and parameter.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }


def load_pilot_service(
    environment: Mapping[str, str] | None = None,
) -> PilotServiceAdapter:
    """Carrega o serviço real somente quando a aplicação web é iniciada."""

    selected_environment = os.environ if environment is None else environment
    service_type = _pilot_symbol("PilotService")
    from_environment = getattr(service_type, "from_environment", None)
    if callable(from_environment):
        service = from_environment()
    else:
        service = service_type(**_constructor_kwargs(service_type, selected_environment))
    return PilotServiceAdapter(service)


__all__ = [
    "DEFAULT_DB_PATH",
    "DEFAULT_RUN_DIR",
    "DEFAULT_SNAPSHOT_DIR",
    "PilotServiceAdapter",
    "PilotServiceProtocol",
    "load_pilot_service",
]
