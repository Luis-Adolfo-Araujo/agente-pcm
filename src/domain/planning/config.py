"""Configuração versionável das regras determinísticas de planejamento."""

from pydantic import Field

from domain.planning.entities import ContractModel


class RankingConfig(ContractModel):
    priority_scores: dict[int, float] = {1: 100, 2: 75, 3: 50, 4: 25}
    priority_weight: float = Field(default=0.35, ge=0)
    age_weight: float = Field(default=0.25, ge=0)
    sla_weight: float = Field(default=0.40, ge=0)
    criticality_weight: float = Field(default=0.20, ge=0)
    age_cap_days: int = Field(default=90, gt=0)
    sla_horizon_days: int = Field(default=45, gt=0)
    overdue_cap_days: int = Field(default=45, gt=0)


class DurationConfig(ContractModel):
    prefer_planned: bool = True
    minimum_sample_size: int = Field(default=3, ge=1)
    maximum_valid_minutes: int = Field(default=24 * 60, gt=0)
    default_minutes: int | None = Field(default=60, gt=0)
    title_similarity_threshold: float = Field(default=0.45, ge=0, le=1)


class MaterialConfig(ContractModel):
    consider_expected_inbound: bool = True
    allow_partial: bool = False
    # Uma OS sem material cadastrado não declara dispensa de material: no Planta Modelo
    # ela costuma indicar diagnóstico pendente ou item indisponível. O status é
    # sempre "desconhecido"; esta chave decide se isso impede a programação.
    block_unregistered_material: bool = False


class ExecutantConfig(ContractModel):
    top_n: int = Field(default=5, ge=1, le=50)
    team_weight: float = Field(default=20, ge=0)
    asset_weight: float = Field(default=30, ge=0)
    activity_weight: float = Field(default=25, ge=0)
    location_weight: float = Field(default=15, ge=0)
    frequency_weight: float = Field(default=10, ge=0)


class OptimizerConfig(ContractModel):
    algorithm_version: str = "greedy-v1"
    slot_granularity_minutes: int = Field(default=15, gt=0)


class PlanningConfig(ContractModel):
    ranking: RankingConfig = RankingConfig()
    duration: DurationConfig = DurationConfig()
    materials: MaterialConfig = MaterialConfig()
    executants: ExecutantConfig = ExecutantConfig()
    optimizer: OptimizerConfig = OptimizerConfig()
