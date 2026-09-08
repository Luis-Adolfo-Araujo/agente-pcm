from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from agent.skills.core.discovery import discover_skills, read_skill_manifest
from agent.skills.core.loader import load_skill, resolve_skill_reference
from agent.skills.core.models import (
    SkillBodyTooLargeError,
    SkillChangedError,
    SkillCollisionError,
    SkillNotFoundError,
    SkillSecurityError,
    SkillValidationError,
)
from agent.skills.core.registry import SkillRegistry


def write_skill(
    root: Path,
    directory: str,
    *,
    name: str,
    description: str = "A useful test skill.",
    body: str = "# Instructions\n\nDo the deterministic thing.\n",
) -> Path:
    skill_directory = root / directory
    skill_directory.mkdir(parents=True, exist_ok=True)
    path = skill_directory / "SKILL.md"
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}",
        encoding="utf-8",
    )
    return path


def test_repository_registry_discovers_and_loads_the_five_pcm_skills() -> None:
    project_root = Path(__file__).resolve().parents[3]
    registry = SkillRegistry.from_directory(project_root / "src/agent/skills/pcm")

    assert registry.names == (
        "calculate-capacity",
        "check-materials",
        "estimate-duration",
        "rank-backlog",
        "suggest-executants",
    )
    assert all(metadata.description for metadata in registry.list_metadata())
    assert {skill.name for skill in registry.load_all()} == set(registry.names)
    assert all(len(skill.content_hash) == 64 for skill in registry.load_all())


def test_discovery_reads_frontmatter_without_applying_body_limit(tmp_path: Path) -> None:
    write_skill(tmp_path, "large", name="large", body="x" * 100)

    manifest = discover_skills(tmp_path)[0]

    assert manifest.name == "large"
    with pytest.raises(SkillBodyTooLargeError, match="exceeds 10 bytes"):
        load_skill(manifest, max_body_bytes=10)


@pytest.mark.parametrize(
    "frontmatter, expected",
    [
        ("description: missing name", "'name' must be a string"),
        ("name: missing-description", "'description' must be a string"),
        ("name: ../escape\ndescription: nope", "unsafe skill name"),
        ("name: Uppercase\ndescription: nope", "lowercase letters"),
        ("name: false\ndescription: nope", "'name' must be a string"),
    ],
)
def test_invalid_frontmatter_is_rejected(
    tmp_path: Path,
    frontmatter: str,
    expected: str,
) -> None:
    skill_directory = tmp_path / "invalid"
    skill_directory.mkdir()
    (skill_directory / "SKILL.md").write_text(
        f"---\n{frontmatter}\n---\nbody",
        encoding="utf-8",
    )

    with pytest.raises((SkillValidationError, SkillSecurityError), match=expected):
        discover_skills(tmp_path)


def test_yaml_unsafe_python_tag_is_rejected(tmp_path: Path) -> None:
    skill_directory = tmp_path / "unsafe-yaml"
    skill_directory.mkdir()
    (skill_directory / "SKILL.md").write_text(
        "---\n"
        "name: unsafe-yaml\n"
        "description: !!python/object/apply:builtins.str [unsafe]\n"
        "---\nbody\n",
        encoding="utf-8",
    )

    with pytest.raises(SkillValidationError, match="invalid YAML"):
        discover_skills(tmp_path)


def test_duplicate_names_are_rejected_with_both_paths(tmp_path: Path) -> None:
    first = write_skill(tmp_path, "first", name="duplicate")
    second = write_skill(tmp_path, "second", name="duplicate")

    with pytest.raises(SkillCollisionError) as raised:
        discover_skills(tmp_path)

    assert str(first.resolve()) in str(raised.value)
    assert str(second.resolve()) in str(raised.value)


def test_cross_root_collision_is_rejected(tmp_path: Path) -> None:
    first_root = tmp_path / "first-root"
    second_root = tmp_path / "second-root"
    write_skill(first_root, "one", name="same")
    write_skill(second_root, "two", name="same")

    with pytest.raises(SkillCollisionError, match="duplicate skill name"):
        SkillRegistry.from_directories((first_root, second_root))


def test_manifest_outside_root_and_symlink_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside_manifest = write_skill(outside, "external", name="external")

    with pytest.raises(SkillSecurityError, match="manifest"):
        read_skill_manifest(outside_manifest, root)

    linked_directory = root / "linked"
    linked_directory.mkdir()
    (linked_directory / "SKILL.md").symlink_to(outside_manifest)
    with pytest.raises(SkillSecurityError, match="symlink"):
        discover_skills(root)


def test_hash_and_version_are_content_addressed(tmp_path: Path) -> None:
    path = write_skill(tmp_path, "versioned", name="versioned", body="first")
    manifest = discover_skills(tmp_path)[0]

    first = load_skill(manifest)
    assert first.content_hash == hashlib.sha256(path.read_bytes()).hexdigest()
    assert first.version == first.content_hash[:16]

    path.write_text(
        "---\nname: versioned\ndescription: A useful test skill.\n---\nsecond",
        encoding="utf-8",
    )
    second = load_skill(manifest)
    assert second.body == "second"
    assert second.content_hash != first.content_hash
    assert second.version != first.version


def test_metadata_drift_after_discovery_is_rejected(tmp_path: Path) -> None:
    path = write_skill(tmp_path, "versioned", name="versioned")
    manifest = discover_skills(tmp_path)[0]
    path.write_text(
        "---\nname: renamed\ndescription: A useful test skill.\n---\nbody",
        encoding="utf-8",
    )

    with pytest.raises(SkillChangedError, match="changed after discovery"):
        load_skill(manifest)


def test_registry_filters_disabled_skills_without_loading_them(tmp_path: Path) -> None:
    write_skill(tmp_path, "enabled", name="enabled")
    write_skill(tmp_path, "disabled", name="disabled", body="x" * 100)
    registry = SkillRegistry.from_directory(
        tmp_path,
        enabled=("enabled",),
        max_body_bytes=10,
    )

    assert registry.enabled_names == ("enabled",)
    assert tuple(registry.catalog) == ("enabled",)
    with pytest.raises(SkillNotFoundError, match="disabled"):
        registry.load("disabled")

    registry.enable("disabled")
    with pytest.raises(SkillBodyTooLargeError):
        registry.load("disabled")


def test_unknown_and_traversal_lookups_are_rejected(tmp_path: Path) -> None:
    write_skill(tmp_path, "known", name="known")
    registry = SkillRegistry.from_directory(tmp_path)

    with pytest.raises(SkillNotFoundError, match="unknown"):
        registry.load("missing")
    with pytest.raises(SkillSecurityError, match="unsafe skill name"):
        registry.load("../known")


def test_references_are_confined_to_the_own_skill_directory(tmp_path: Path) -> None:
    manifest_path = write_skill(tmp_path, "skill", name="skill")
    reference = manifest_path.parent / "references" / "rules.md"
    reference.parent.mkdir()
    reference.write_text("rules", encoding="utf-8")
    sibling = tmp_path / "secret.md"
    sibling.write_text("secret", encoding="utf-8")
    manifest = discover_skills(tmp_path)[0]

    assert resolve_skill_reference(manifest, "references/rules.md") == reference.resolve()
    with pytest.raises(SkillSecurityError, match="unsafe skill reference"):
        resolve_skill_reference(manifest, "../secret.md")


def test_frontmatter_and_body_must_be_valid_utf8(tmp_path: Path) -> None:
    directory = tmp_path / "binary"
    directory.mkdir()
    path = directory / "SKILL.md"
    path.write_bytes(b"---\nname: binary\ndescription: \xff\n---\nbody")
    with pytest.raises(SkillValidationError, match="frontmatter is not valid UTF-8"):
        discover_skills(tmp_path)

    path.write_bytes(b"---\nname: binary\ndescription: valid\n---\n\xff")
    manifest = discover_skills(tmp_path)[0]
    with pytest.raises(SkillValidationError, match="body is not valid UTF-8"):
        load_skill(manifest)


def test_size_limits_are_validated_even_for_an_empty_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="max_frontmatter_bytes"):
        discover_skills(tmp_path, max_frontmatter_bytes=0)
    with pytest.raises(ValueError, match="max_body_bytes"):
        SkillRegistry.from_directory(tmp_path, max_body_bytes=0)
