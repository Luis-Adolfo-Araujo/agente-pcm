from pathlib import Path

from application.config import (
    derive_weights_version,
    load_planning_config,
    planning_config_hash,
)
from domain.planning.config import PlanningConfig, RankingConfig


def test_config_hash_is_stable_across_mapping_insertion_order() -> None:
    ascending = PlanningConfig(
        ranking=RankingConfig(priority_scores={1: 100, 2: 75, 3: 50, 4: 25})
    )
    descending = PlanningConfig(
        ranking=RankingConfig(priority_scores={4: 25, 3: 50, 2: 75, 1: 100})
    )

    assert planning_config_hash(ascending) == planning_config_hash(descending)
    assert derive_weights_version(ascending) == derive_weights_version(descending)


def test_config_version_changes_when_any_planning_setting_changes() -> None:
    baseline = PlanningConfig()
    changed = PlanningConfig(
        ranking=RankingConfig(priority_weight=0.36),
    )

    assert planning_config_hash(baseline) != planning_config_hash(changed)
    version = derive_weights_version(baseline)
    assert version == f"sha256:{planning_config_hash(baseline)}"
    assert len(version) == len("sha256:") + 64


def test_shipped_tenant_configs_are_valid() -> None:
    """Uma chave em seção errada precisa quebrar aqui, não no piloto."""

    tenant_dir = Path(__file__).resolve().parents[3] / "config" / "tenants"
    configs = sorted(tenant_dir.glob("*.yaml"))

    assert configs, "nenhuma configuração de tenant encontrada"
    for path in configs:
        loaded = load_planning_config(path)
        assert loaded.ranking.priority_weight >= 0
        assert loaded.materials.block_unregistered_material in {True, False}
