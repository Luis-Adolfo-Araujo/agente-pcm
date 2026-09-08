"""Lazy catalogue for discovered, enabled filesystem skills."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from threading import RLock

from agent.skills.core.discovery import (
    DEFAULT_MAX_FRONTMATTER_BYTES,
    discover_skills,
)
from agent.skills.core.loader import DEFAULT_MAX_BODY_BYTES, SkillLoader
from agent.skills.core.models import (
    LoadedSkill,
    SkillCollisionError,
    SkillManifest,
    SkillMetadata,
    SkillNotFoundError,
    validate_skill_name,
)


class SkillRegistry:
    """A deterministic catalogue that loads enabled skill bodies on demand."""

    def __init__(
        self,
        manifests: Iterable[SkillManifest],
        *,
        enabled: Iterable[str] | None = None,
        max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
        max_frontmatter_bytes: int = DEFAULT_MAX_FRONTMATTER_BYTES,
    ) -> None:
        if isinstance(max_body_bytes, bool) or not isinstance(max_body_bytes, int):
            raise ValueError("max_body_bytes must be a positive integer")
        if max_body_bytes <= 0:
            raise ValueError("max_body_bytes must be a positive integer")
        if isinstance(max_frontmatter_bytes, bool) or not isinstance(max_frontmatter_bytes, int):
            raise ValueError("max_frontmatter_bytes must be a positive integer")
        if max_frontmatter_bytes <= 0:
            raise ValueError("max_frontmatter_bytes must be a positive integer")

        catalogue: dict[str, SkillManifest] = {}
        for manifest in manifests:
            previous = catalogue.get(manifest.name)
            if previous is not None:
                raise SkillCollisionError(
                    f"duplicate skill name {manifest.name!r}: "
                    f"{previous.path} and {manifest.path}"
                )
            catalogue[manifest.name] = manifest

        requested_enabled = set(catalogue) if enabled is None else {
            validate_skill_name(name) for name in enabled
        }
        unknown = requested_enabled.difference(catalogue)
        if unknown:
            rendered = ", ".join(sorted(unknown))
            raise SkillNotFoundError(f"cannot enable unknown skills: {rendered}")

        self._manifests = dict(sorted(catalogue.items()))
        self._enabled = requested_enabled
        self._loaders = {
            manifest.root: SkillLoader(
                manifest.root,
                max_body_bytes=max_body_bytes,
                max_frontmatter_bytes=max_frontmatter_bytes,
            )
            for manifest in self._manifests.values()
        }
        self._loaded: dict[str, LoadedSkill] = {}
        self._lock = RLock()

    @classmethod
    def from_directory(
        cls,
        root: str | Path,
        *,
        enabled: Iterable[str] | None = None,
        max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
        max_frontmatter_bytes: int = DEFAULT_MAX_FRONTMATTER_BYTES,
    ) -> SkillRegistry:
        """Discover one root and build a registry."""

        manifests = discover_skills(
            root,
            max_frontmatter_bytes=max_frontmatter_bytes,
        )
        return cls(
            manifests,
            enabled=enabled,
            max_body_bytes=max_body_bytes,
            max_frontmatter_bytes=max_frontmatter_bytes,
        )

    @classmethod
    def from_directories(
        cls,
        roots: Iterable[str | Path],
        *,
        enabled: Iterable[str] | None = None,
        max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
        max_frontmatter_bytes: int = DEFAULT_MAX_FRONTMATTER_BYTES,
    ) -> SkillRegistry:
        """Discover several roots, rejecting cross-root name collisions."""

        manifests: list[SkillManifest] = []
        seen_roots: set[Path] = set()
        for root in roots:
            resolved_root = Path(root).resolve(strict=True)
            if resolved_root in seen_roots:
                continue
            seen_roots.add(resolved_root)
            manifests.extend(
                discover_skills(
                    resolved_root,
                    max_frontmatter_bytes=max_frontmatter_bytes,
                )
            )
        return cls(
            manifests,
            enabled=enabled,
            max_body_bytes=max_body_bytes,
            max_frontmatter_bytes=max_frontmatter_bytes,
        )

    @property
    def names(self) -> tuple[str, ...]:
        """Return every registered name in stable order."""

        return tuple(self._manifests)

    @property
    def enabled_names(self) -> tuple[str, ...]:
        """Return enabled names in stable catalogue order."""

        return tuple(name for name in self._manifests if name in self._enabled)

    @property
    def catalog(self) -> Mapping[str, SkillMetadata]:
        """Expose a copy of enabled metadata suitable for context assembly."""

        return {
            name: manifest.metadata
            for name, manifest in self._manifests.items()
            if name in self._enabled
        }

    def list_metadata(self, *, enabled_only: bool = True) -> tuple[SkillMetadata, ...]:
        """List metadata without loading any Markdown body."""

        return tuple(
            manifest.metadata
            for name, manifest in self._manifests.items()
            if not enabled_only or name in self._enabled
        )

    def is_enabled(self, name: str) -> bool:
        canonical = validate_skill_name(name)
        return canonical in self._enabled

    def enable(self, name: str) -> None:
        canonical = self._known_name(name)
        with self._lock:
            self._enabled.add(canonical)

    def disable(self, name: str) -> None:
        canonical = self._known_name(name)
        with self._lock:
            self._enabled.discard(canonical)

    def get_manifest(self, name: str, *, include_disabled: bool = False) -> SkillManifest:
        """Look up a manifest, enforcing activation by default."""

        canonical = self._known_name(name)
        if not include_disabled and canonical not in self._enabled:
            raise SkillNotFoundError(f"skill is disabled: {canonical}")
        return self._manifests[canonical]

    def load(self, name: str) -> LoadedSkill:
        """Load and cache one enabled skill."""

        manifest = self.get_manifest(name)
        with self._lock:
            cached = self._loaded.get(manifest.name)
            if cached is not None:
                return cached
            loaded = self._loaders[manifest.root].load(manifest)
            self._loaded[manifest.name] = loaded
            return loaded

    get = load

    def reload(self, name: str) -> LoadedSkill:
        """Reload an enabled skill and replace its cached body/version."""

        manifest = self.get_manifest(name)
        with self._lock:
            loaded = self._loaders[manifest.root].load(manifest)
            self._loaded[manifest.name] = loaded
            return loaded

    def load_all(self) -> tuple[LoadedSkill, ...]:
        """Load every enabled skill in stable order."""

        return tuple(self.load(name) for name in self.enabled_names)

    def _known_name(self, name: str) -> str:
        canonical = validate_skill_name(name)
        if canonical not in self._manifests:
            raise SkillNotFoundError(f"unknown skill: {canonical}")
        return canonical

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        try:
            canonical = validate_skill_name(name)
        except ValueError:
            return False
        return canonical in self._manifests

    def __iter__(self) -> Iterator[str]:
        return iter(self._manifests)

    def __len__(self) -> int:
        return len(self._manifests)


def build_skill_registry(
    root: str | Path,
    *,
    enabled: Iterable[str] | None = None,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
) -> SkillRegistry:
    """Small convenience entry point for application wiring."""

    return SkillRegistry.from_directory(
        root,
        enabled=enabled,
        max_body_bytes=max_body_bytes,
    )
