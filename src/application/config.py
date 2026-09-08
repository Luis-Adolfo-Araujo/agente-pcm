"""Carregamento seguro da configuração versionada do planejador."""

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from domain.planning.config import PlanningConfig


def planning_config_hash(config: PlanningConfig) -> str:
    """Return a deterministic SHA-256 digest of the complete validated config."""

    canonical = json.dumps(
        config.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def derive_weights_version(config: PlanningConfig) -> str:
    """Build the request version used to bind a proposal to its full config."""

    return f"sha256:{planning_config_hash(config)}"


def load_planning_config(path: Path | None) -> PlanningConfig:
    if path is None:
        return PlanningConfig()
    payload: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("planning config must be a YAML mapping")
    return PlanningConfig.model_validate(payload)
