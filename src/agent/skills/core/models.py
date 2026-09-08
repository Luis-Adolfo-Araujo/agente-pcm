"""Typed records and errors used by the filesystem skill catalogue."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SKILL_FILENAME = "SKILL.md"
MAX_SKILL_NAME_LENGTH = 64
MAX_SKILL_DESCRIPTION_LENGTH = 1024

_SKILL_NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class SkillError(Exception):
    """Base error for skill discovery, loading, and lookup."""


class SkillValidationError(SkillError, ValueError):
    """Raised when a skill manifest or its content is invalid."""


class SkillSecurityError(SkillError, ValueError):
    """Raised when a filesystem operation would escape its allowed directory."""


class SkillCollisionError(SkillValidationError):
    """Raised when more than one manifest declares the same skill name."""


class SkillNotFoundError(SkillError, LookupError):
    """Raised when a requested skill is not present or not enabled."""


class SkillBodyTooLargeError(SkillValidationError):
    """Raised when a skill body exceeds the configured byte limit."""


class SkillChangedError(SkillValidationError):
    """Raised when a manifest changes between discovery and loading."""


def validate_skill_name(name: object) -> str:
    """Return a canonical skill name or raise a validation/security error."""

    if not isinstance(name, str):
        raise SkillValidationError("skill frontmatter 'name' must be a string")
    if not name:
        raise SkillValidationError("skill frontmatter 'name' must not be empty")
    if name != name.strip():
        raise SkillValidationError(
            "skill frontmatter 'name' must not contain surrounding whitespace"
        )
    if "/" in name or "\\" in name or name in {".", ".."}:
        raise SkillSecurityError(f"unsafe skill name: {name!r}")
    if len(name) > MAX_SKILL_NAME_LENGTH:
        raise SkillValidationError(
            f"skill frontmatter 'name' must be at most {MAX_SKILL_NAME_LENGTH} characters"
        )
    if _SKILL_NAME_PATTERN.fullmatch(name) is None:
        raise SkillValidationError(
            "skill frontmatter 'name' must contain only lowercase letters, digits, and "
            "single hyphens"
        )
    return name


def validate_skill_description(description: object) -> str:
    """Return a trimmed, non-empty skill description."""

    if not isinstance(description, str):
        raise SkillValidationError("skill frontmatter 'description' must be a string")
    normalized = description.strip()
    if not normalized:
        raise SkillValidationError("skill frontmatter 'description' must not be empty")
    if "\x00" in normalized:
        raise SkillValidationError("skill frontmatter 'description' contains a null byte")
    if len(normalized) > MAX_SKILL_DESCRIPTION_LENGTH:
        raise SkillValidationError(
            "skill frontmatter 'description' must be at most "
            f"{MAX_SKILL_DESCRIPTION_LENGTH} characters"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    """The small frontmatter subset safe to expose during discovery."""

    name: str
    description: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", validate_skill_name(self.name))
        object.__setattr__(
            self,
            "description",
            validate_skill_description(self.description),
        )


@dataclass(frozen=True, slots=True)
class SkillManifest:
    """A discovered manifest without its potentially large Markdown body."""

    metadata: SkillMetadata
    path: Path
    root: Path
    body_offset: int

    def __post_init__(self) -> None:
        if self.body_offset <= 0:
            raise SkillValidationError("skill body offset must be positive")
        if self.path.name != SKILL_FILENAME:
            raise SkillValidationError(f"skill manifest must be named {SKILL_FILENAME}")

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def description(self) -> str:
        return self.metadata.description

    @property
    def directory(self) -> Path:
        return self.path.parent


@dataclass(frozen=True, slots=True)
class LoadedSkill:
    """A fully loaded and content-addressed skill."""

    manifest: SkillManifest
    body: str
    content_hash: str
    version: str

    def __post_init__(self) -> None:
        if _SHA256_PATTERN.fullmatch(self.content_hash) is None:
            raise SkillValidationError("skill content_hash must be a lowercase SHA-256 digest")
        if not self.version:
            raise SkillValidationError("skill version must not be empty")

    @property
    def metadata(self) -> SkillMetadata:
        return self.manifest.metadata

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def description(self) -> str:
        return self.manifest.description

    @property
    def path(self) -> Path:
        return self.manifest.path
