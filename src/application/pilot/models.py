"""Contratos serializáveis da camada de serviço do piloto."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from domain.planning.config import PlanningConfig
from domain.planning.entities import (
    ContractModel,
    HumanDecision,
    PlanningRequest,
    PlanningStageTrace,
)


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class FeedbackSkill(StrEnum):
    RANKING = "ranking"
    DURATION = "duration"
    MATERIALS = "materials"
    EXECUTANTS = "executants"
    SCHEDULE = "schedule"


class FeedbackVerdict(StrEnum):
    CORRECT = "correct"
    ACCEPTABLE = "acceptable"
    INCORRECT = "incorrect"


class ExportFormat(StrEnum):
    JSON = "json"
    CSV = "csv"


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("datetime must include a timezone")
    return value


class CoverageIndicator(ContractModel):
    key: str = Field(min_length=1)
    present: int = Field(ge=0)
    total: int = Field(ge=0)
    missing: int = Field(ge=0)
    coverage_percent: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def counts_are_consistent(self) -> CoverageIndicator:
        if self.present + self.missing != self.total:
            raise ValueError("coverage counts must add up to total")
        return self


class SnapshotQuality(ContractModel):
    operation_count: int = Field(ge=0)
    historical_execution_count: int = Field(ge=0)
    inventory_item_count: int = Field(ge=0)
    worker_count: int = Field(ge=0)
    availability_slot_count: int = Field(ge=0)
    material_requirement_count: int = Field(ge=0)
    rejected_record_count: int = Field(ge=0)
    indicators: tuple[CoverageIndicator, ...]


class CapacityCoverage(ContractModel):
    """Quanto da demanda do backlog a capacidade disponível comporta."""

    total_operations: int = Field(ge=0)
    scheduled_operations: int = Field(ge=0)
    unscheduled_operations: int = Field(ge=0)
    capacity_limited_operations: int = Field(ge=0)
    demand_minutes: int = Field(ge=0)
    available_minutes: int = Field(ge=0)
    coverage_percent: float = Field(ge=0, le=100)
    reasons: dict[str, int] = Field(default_factory=dict)


class SnapshotSummary(ContractModel):
    snapshot_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    as_of: datetime
    schema_version: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=1)
    source: str | None = None
    latest_ingestion: str | None = None
    quality: SnapshotQuality

    @field_validator("as_of")
    @classmethod
    def as_of_is_aware(cls, value: datetime) -> datetime:
        checked = _aware(value)
        assert checked is not None
        return checked


class RunSummary(ContractModel):
    proposal_status: str
    verification_valid: bool
    assignments: int = Field(ge=0)
    unscheduled: int = Field(ge=0)
    violations: int = Field(ge=0)
    objective_value: float
    trace_elapsed_ms: float = Field(default=0, ge=0)


class PilotRun(ContractModel):
    run_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    status: RunStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    request: PlanningRequest
    config: PlanningConfig
    proposal_id: str | None = None
    summary: RunSummary | None = None
    error: str | None = None
    current_stage: str | None = None
    trace_events: tuple[PlanningStageTrace, ...] = ()
    artifact_names: tuple[str, ...] = ()
    decision: HumanDecision | None = None

    @field_validator("created_at", "started_at", "completed_at")
    @classmethod
    def timestamps_are_aware(cls, value: datetime | None) -> datetime | None:
        return _aware(value)

    @model_validator(mode="after")
    def state_shape_is_consistent(self) -> PilotRun:
        if self.status is RunStatus.QUEUED:
            if self.started_at is not None or self.completed_at is not None:
                raise ValueError("queued run cannot have execution timestamps")
        elif self.status is RunStatus.RUNNING:
            if self.started_at is None or self.completed_at is not None:
                raise ValueError("running run must only have started_at")
        else:
            if self.completed_at is None:
                raise ValueError("terminal run must have completed_at")
        if self.status is RunStatus.COMPLETED and (
            self.proposal_id is None or self.summary is None or self.error is not None
        ):
            raise ValueError("completed run must contain a result and no error")
        if self.status in {RunStatus.FAILED, RunStatus.INTERRUPTED} and not self.error:
            raise ValueError("failed or interrupted run must contain a sanitized error")
        return self


class FeedbackInput(ContractModel):
    operation_id: str = Field(min_length=1)
    skill: FeedbackSkill
    verdict: FeedbackVerdict
    reason: str = Field(min_length=1, max_length=2000)


class FeedbackRecord(ContractModel):
    feedback_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    skill: FeedbackSkill
    verdict: FeedbackVerdict
    reason: str = Field(min_length=1, max_length=2000)
    recorded_by: str = Field(min_length=1, max_length=200)
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def recorded_at_is_aware(cls, value: datetime) -> datetime:
        checked = _aware(value)
        assert checked is not None
        return checked


class ExportBundle(ContractModel):
    run_id: str = Field(min_length=1)
    format: ExportFormat
    files: dict[str, str]
    media_types: dict[str, str]

    @model_validator(mode="after")
    def every_file_has_a_media_type(self) -> ExportBundle:
        if set(self.files) != set(self.media_types):
            raise ValueError("every exported file must have one media type")
        return self
