"""Pseudonimização e autenticação simples da interface piloto."""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import re
from collections.abc import Mapping
from typing import Any

SHOW_RAW_WORKERS_ENV = "MAIA_PILOT_SHOW_RAW_WORKER_IDS"
ALIAS_SALT_ENV = "MAIA_PILOT_ALIAS_SALT"
ALLOW_ANONYMOUS_ENV = "MAIA_PILOT_ALLOW_ANONYMOUS"
_DEFAULT_ALIAS_SALT = "maia-pilot-worker-alias-v1"
_TRUE_VALUES = frozenset({"1", "on", "sim", "true", "yes"})
_SINGULAR_WORKER_KEYS = frozenset(
    {
        "assigned_worker",
        "executant",
        "executante",
        "executor",
        "worker",
        "worker_id",
    }
)
_PLURAL_WORKER_KEYS = frozenset(
    {
        "assigned_workers",
        "executants",
        "executantes",
        "executors",
        "worker_ids",
        "workers",
    }
)


def raw_worker_ids_enabled(environment: Mapping[str, str]) -> bool:
    """Libera identificadores de origem somente por opt-in explícito."""

    return environment.get(SHOW_RAW_WORKERS_ENV, "").strip().casefold() in _TRUE_VALUES


def anonymous_access_enabled(environment: Mapping[str, str]) -> bool:
    """Exige um opt-in separado quando não houver senha configurada."""

    return environment.get(ALLOW_ANONYMOUS_ENV, "").strip().casefold() in _TRUE_VALUES


def worker_alias(
    worker_id: str,
    *,
    salt: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> str:
    """Cria um alias curto e determinístico sem persistir o identificador cru."""

    if worker_id.startswith("Técnico-"):
        return worker_id
    selected_salt = salt
    if selected_salt is None and environment is not None:
        selected_salt = environment.get(ALIAS_SALT_ENV)
    digest = hashlib.sha256(
        f"{selected_salt or _DEFAULT_ALIAS_SALT}\0{worker_id}".encode()
    ).hexdigest()[:8]
    return f"Técnico-{digest.upper()}"


def display_worker_id(
    worker_id: str,
    *,
    reveal: bool = False,
    salt: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> str:
    if reveal:
        return worker_id
    return worker_alias(worker_id, salt=salt, environment=environment)


def password_is_valid(expected: str | None, supplied: str) -> bool:
    """Compara a senha sem diferença de tempo observável."""

    if not expected:
        return True
    return hmac.compare_digest(expected.encode("utf-8"), supplied.encode("utf-8"))


def _normalized_key(value: object) -> str:
    return str(value).strip().casefold().replace("-", "_").replace(" ", "_")


def _pseudonymize_compound(
    value: str,
    *,
    salt: str | None,
    environment: Mapping[str, str] | None,
) -> str:
    stripped = value.strip()
    if not stripped:
        return value
    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return json.dumps(
                [
                    worker_alias(str(item), salt=salt, environment=environment)
                    for item in parsed
                ],
                ensure_ascii=False,
            )

    parts = re.split(r"([,;|])", value)
    return "".join(
        part
        if part in {",", ";", "|"} or not part.strip()
        else worker_alias(part.strip(), salt=salt, environment=environment)
        for part in parts
    )


def pseudonymize_worker_fields(
    value: Any,
    *,
    reveal: bool = False,
    salt: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> Any:
    """Copia uma estrutura trocando apenas campos semanticamente de pessoa."""

    if reveal:
        return value
    if isinstance(value, Mapping):
        result: dict[Any, Any] = {}
        for key, item in value.items():
            normalized = _normalized_key(key)
            if normalized in _SINGULAR_WORKER_KEYS and item is not None:
                result[key] = worker_alias(str(item), salt=salt, environment=environment)
            elif normalized in _PLURAL_WORKER_KEYS and isinstance(item, str):
                result[key] = _pseudonymize_compound(
                    item,
                    salt=salt,
                    environment=environment,
                )
            elif normalized in _PLURAL_WORKER_KEYS and isinstance(item, (list, tuple)):
                # "executants" às vezes é uma lista de nomes e às vezes uma lista de
                # candidatos com score, elegibilidade e evidências. Trocar o registro
                # inteiro por um alias apagaria a saída da skill, então só o que é
                # identificador vira alias; o resto desce recursivamente.
                aliases = [
                    pseudonymize_worker_fields(entry, salt=salt, environment=environment)
                    if isinstance(entry, (Mapping, list, tuple))
                    else worker_alias(str(entry), salt=salt, environment=environment)
                    for entry in item
                ]
                result[key] = tuple(aliases) if isinstance(item, tuple) else aliases
            else:
                result[key] = pseudonymize_worker_fields(
                    item,
                    salt=salt,
                    environment=environment,
                )
        return result
    if isinstance(value, list):
        return [
            pseudonymize_worker_fields(item, salt=salt, environment=environment)
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            pseudonymize_worker_fields(item, salt=salt, environment=environment)
            for item in value
        )
    return value


def pseudonymize_export(
    payload: bytes,
    export_format: str,
    *,
    reveal: bool = False,
    salt: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> bytes:
    """Sanitiza downloads JSON/CSV antes que deixem a camada de apresentação."""

    if reveal:
        return payload
    normalized_format = export_format.casefold().replace("_", ".")
    if "json" in normalized_format:
        parsed = json.loads(payload.decode("utf-8-sig"))
        sanitized = pseudonymize_worker_fields(
            parsed,
            salt=salt,
            environment=environment,
        )
        return json.dumps(sanitized, ensure_ascii=False, indent=2).encode("utf-8")
    if "csv" not in normalized_format:
        raise ValueError("unsupported export format for safe pseudonymization")

    source = io.StringIO(payload.decode("utf-8-sig"), newline="")
    reader = csv.DictReader(source)
    if reader.fieldnames is None:
        return payload
    destination = io.StringIO(newline="")
    writer = csv.DictWriter(destination, fieldnames=reader.fieldnames)
    writer.writeheader()
    for row in reader:
        sanitized = pseudonymize_worker_fields(
            row,
            salt=salt,
            environment=environment,
        )
        writer.writerow(sanitized)
    return destination.getvalue().encode("utf-8")


__all__ = [
    "ALLOW_ANONYMOUS_ENV",
    "ALIAS_SALT_ENV",
    "SHOW_RAW_WORKERS_ENV",
    "anonymous_access_enabled",
    "display_worker_id",
    "password_is_valid",
    "pseudonymize_export",
    "pseudonymize_worker_fields",
    "raw_worker_ids_enabled",
    "worker_alias",
]
