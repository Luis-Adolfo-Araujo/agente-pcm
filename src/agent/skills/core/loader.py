"""Bounded and path-safe loading of discovered skills."""

from __future__ import annotations

import hashlib
from pathlib import Path

from agent.skills.core.discovery import (
    DEFAULT_MAX_FRONTMATTER_BYTES,
    read_skill_manifest,
)
from agent.skills.core.models import (
    LoadedSkill,
    SkillBodyTooLargeError,
    SkillChangedError,
    SkillManifest,
    SkillSecurityError,
    SkillValidationError,
)

DEFAULT_MAX_BODY_BYTES = 64 * 1024
VERSION_DIGEST_LENGTH = 16


def _validate_limit(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def load_skill(
    manifest: SkillManifest,
    *,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
    max_frontmatter_bytes: int = DEFAULT_MAX_FRONTMATTER_BYTES,
) -> LoadedSkill:
    """Load a discovered skill, bound its body, and assign a content version."""

    body_limit = _validate_limit(max_body_bytes, "max_body_bytes")
    frontmatter_limit = _validate_limit(max_frontmatter_bytes, "max_frontmatter_bytes")

    # Re-read the small manifest to defend against path substitution and metadata drift
    # between catalogue discovery and lazy body loading.
    current = read_skill_manifest(
        manifest.path,
        manifest.root,
        max_frontmatter_bytes=frontmatter_limit,
    )
    if current.metadata != manifest.metadata:
        raise SkillChangedError(
            f"skill metadata changed after discovery: {manifest.path}"
        )

    try:
        with current.path.open("rb") as stream:
            prefix = stream.read(current.body_offset)
            if len(prefix) != current.body_offset:
                raise SkillChangedError(
                    f"skill changed while it was being loaded: {current.path}"
                )
            body_bytes = stream.read(body_limit + 1)
    except OSError as exc:
        raise SkillValidationError(f"could not load skill: {current.path}") from exc

    if len(body_bytes) > body_limit:
        raise SkillBodyTooLargeError(
            f"skill body exceeds {body_limit} bytes: {current.path}"
        )
    try:
        body = body_bytes.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise SkillValidationError(f"skill body is not valid UTF-8: {current.path}") from exc

    digest = hashlib.sha256(prefix + body_bytes).hexdigest()
    return LoadedSkill(
        manifest=current,
        body=body,
        content_hash=digest,
        version=digest[:VERSION_DIGEST_LENGTH],
    )


def resolve_skill_reference(
    skill: SkillManifest | LoadedSkill,
    reference: str | Path,
) -> Path:
    """Resolve a referenced file without allowing escape from the skill directory."""

    manifest = skill.manifest if isinstance(skill, LoadedSkill) else skill
    requested = Path(reference)
    rendered = str(reference)
    portable_parts = rendered.replace("\\", "/").split("/")
    if (
        not rendered
        or "\x00" in rendered
        or requested.is_absolute()
        or ".." in portable_parts
        or rendered.startswith("\\")
    ):
        raise SkillSecurityError(f"unsafe skill reference: {reference!r}")

    allowed_directory = manifest.directory.resolve(strict=True)
    candidate = allowed_directory / requested
    cursor = allowed_directory
    for part in requested.parts:
        if part in {"", "."}:
            continue
        cursor = cursor / part
        if cursor.is_symlink():
            raise SkillSecurityError(f"skill reference uses a symlink: {reference!r}")

    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(allowed_directory)
    except (OSError, RuntimeError, ValueError) as exc:
        raise SkillSecurityError(
            f"skill reference escapes its directory or does not exist: {reference!r}"
        ) from exc
    if not resolved.is_file():
        raise SkillValidationError(f"skill reference is not a regular file: {resolved}")
    return resolved


class SkillLoader:
    """Loader bound to a single authorized discovery root."""

    def __init__(
        self,
        root: str | Path,
        *,
        max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
        max_frontmatter_bytes: int = DEFAULT_MAX_FRONTMATTER_BYTES,
    ) -> None:
        requested_root = Path(root)
        try:
            self._root = requested_root.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise SkillValidationError(f"skill root does not exist: {requested_root}") from exc
        if not self._root.is_dir():
            raise SkillValidationError(f"skill root is not a directory: {self._root}")
        self._max_body_bytes = _validate_limit(max_body_bytes, "max_body_bytes")
        self._max_frontmatter_bytes = _validate_limit(
            max_frontmatter_bytes,
            "max_frontmatter_bytes",
        )

    @property
    def root(self) -> Path:
        return self._root

    def load(self, manifest: SkillManifest) -> LoadedSkill:
        """Load a manifest only when it belongs to this loader's root."""

        if manifest.root != self._root:
            raise SkillSecurityError(
                f"skill manifest belongs to a different root: {manifest.path}"
            )
        return load_skill(
            manifest,
            max_body_bytes=self._max_body_bytes,
            max_frontmatter_bytes=self._max_frontmatter_bytes,
        )

    def load_path(self, path: str | Path) -> LoadedSkill:
        """Discover and load one manifest below this loader's root."""

        manifest = read_skill_manifest(
            path,
            self._root,
            max_frontmatter_bytes=self._max_frontmatter_bytes,
        )
        return self.load(manifest)

    def resolve_reference(
        self,
        skill: SkillManifest | LoadedSkill,
        reference: str | Path,
    ) -> Path:
        """Resolve a skill-local reference after checking loader ownership."""

        manifest = skill.manifest if isinstance(skill, LoadedSkill) else skill
        if manifest.root != self._root:
            raise SkillSecurityError(
                f"skill manifest belongs to a different root: {manifest.path}"
            )
        return resolve_skill_reference(manifest, reference)
