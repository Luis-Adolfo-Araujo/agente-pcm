"""Discover filesystem-backed skills by reading only their YAML frontmatter."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, BinaryIO

import yaml

from agent.skills.core.models import (
    SKILL_FILENAME,
    SkillCollisionError,
    SkillManifest,
    SkillMetadata,
    SkillSecurityError,
    SkillValidationError,
    validate_skill_description,
    validate_skill_name,
)

DEFAULT_MAX_FRONTMATTER_BYTES = 16 * 1024
_FRONTMATTER_DELIMITER = b"---"


def _validate_frontmatter_limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("max_frontmatter_bytes must be a positive integer")
    return value


def _resolved_root(root: str | Path) -> Path:
    requested = Path(root)
    try:
        resolved = requested.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SkillValidationError(f"skill root does not exist: {requested}") from exc
    if not resolved.is_dir():
        raise SkillValidationError(f"skill root is not a directory: {resolved}")
    return resolved


def _has_symlink_component(path: Path, root: Path) -> bool:
    """Check path components without following them first."""

    try:
        relative = path.relative_to(root)
    except ValueError:
        return True

    cursor = root
    for part in relative.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            return True
        cursor = cursor / part
        if cursor.is_symlink():
            return True
    return False


def resolve_manifest_path(path: str | Path, root: str | Path) -> tuple[Path, Path]:
    """Resolve a manifest while ensuring it is a regular file below ``root``."""

    safe_root = _resolved_root(root)
    requested = Path(path)
    candidate = requested if requested.is_absolute() else safe_root / requested

    if _has_symlink_component(candidate, safe_root):
        raise SkillSecurityError(f"skill manifest uses traversal or a symlink: {requested}")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(safe_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise SkillSecurityError(f"skill manifest escapes its root: {requested}") from exc
    if resolved.name != SKILL_FILENAME:
        raise SkillValidationError(f"skill manifest must be named {SKILL_FILENAME}: {resolved}")
    if not resolved.is_file():
        raise SkillValidationError(f"skill manifest is not a regular file: {resolved}")
    return resolved, safe_root


def _read_frontmatter_bytes(
    stream: BinaryIO,
    *,
    path: Path,
    max_frontmatter_bytes: int,
) -> tuple[bytes, int]:
    _validate_frontmatter_limit(max_frontmatter_bytes)

    first_line = stream.readline(len(_FRONTMATTER_DELIMITER) + 3)
    if first_line.rstrip(b"\r\n") != _FRONTMATTER_DELIMITER:
        raise SkillValidationError(f"{path} must start with YAML frontmatter delimited by ---")

    consumed = len(first_line)
    chunks: list[bytes] = []
    while True:
        remaining = max_frontmatter_bytes - consumed
        if remaining <= 0:
            raise SkillValidationError(
                f"skill frontmatter exceeds {max_frontmatter_bytes} bytes: {path}"
            )
        line = stream.readline(remaining + 1)
        if not line:
            raise SkillValidationError(f"skill frontmatter has no closing --- delimiter: {path}")
        if len(line) > remaining:
            raise SkillValidationError(
                f"skill frontmatter exceeds {max_frontmatter_bytes} bytes: {path}"
            )
        consumed += len(line)
        if line.rstrip(b"\r\n") == _FRONTMATTER_DELIMITER:
            return b"".join(chunks), stream.tell()
        chunks.append(line)


def _parse_metadata(frontmatter: bytes, path: Path) -> SkillMetadata:
    try:
        text = frontmatter.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SkillValidationError(f"skill frontmatter is not valid UTF-8: {path}") from exc

    try:
        payload: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SkillValidationError(f"invalid YAML frontmatter in {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise SkillValidationError(f"skill frontmatter must be a YAML mapping: {path}")

    try:
        name = validate_skill_name(payload.get("name"))
        description = validate_skill_description(payload.get("description"))
    except SkillSecurityError as exc:
        raise SkillSecurityError(f"{path}: {exc}") from exc
    except SkillValidationError as exc:
        raise SkillValidationError(f"{path}: {exc}") from exc
    return SkillMetadata(name=name, description=description)


def read_skill_manifest(
    path: str | Path,
    root: str | Path,
    *,
    max_frontmatter_bytes: int = DEFAULT_MAX_FRONTMATTER_BYTES,
) -> SkillManifest:
    """Read and validate one manifest without reading its Markdown body."""

    _validate_frontmatter_limit(max_frontmatter_bytes)
    resolved, safe_root = resolve_manifest_path(path, root)
    try:
        with resolved.open("rb") as stream:
            frontmatter, body_offset = _read_frontmatter_bytes(
                stream,
                path=resolved,
                max_frontmatter_bytes=max_frontmatter_bytes,
            )
    except OSError as exc:
        raise SkillValidationError(f"could not read skill manifest: {resolved}") from exc

    return SkillManifest(
        metadata=_parse_metadata(frontmatter, resolved),
        path=resolved,
        root=safe_root,
        body_offset=body_offset,
    )


def discover_skills(
    root: str | Path,
    *,
    max_frontmatter_bytes: int = DEFAULT_MAX_FRONTMATTER_BYTES,
) -> tuple[SkillManifest, ...]:
    """Discover all ``SKILL.md`` files below a root and reject name collisions."""

    _validate_frontmatter_limit(max_frontmatter_bytes)
    safe_root = _resolved_root(root)
    paths = sorted(safe_root.glob(f"**/{SKILL_FILENAME}"))
    manifests: dict[str, SkillManifest] = {}

    for path in paths:
        manifest = read_skill_manifest(
            path,
            safe_root,
            max_frontmatter_bytes=max_frontmatter_bytes,
        )
        previous = manifests.get(manifest.name)
        if previous is not None:
            raise SkillCollisionError(
                f"duplicate skill name {manifest.name!r}: {previous.path} and {manifest.path}"
            )
        manifests[manifest.name] = manifest

    return tuple(manifests[name] for name in sorted(manifests))


# The longer name reads better at call sites that already use "skill" as a noun.
discover_skill_manifests = discover_skills
