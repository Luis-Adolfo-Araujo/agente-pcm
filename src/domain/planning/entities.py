"""Contratos canônicos do Agente Programador.

Os modelos são imutáveis e rejeitam campos desconhecidos para tornar snapshots e
resultados reproduzíveis. Toda duração canônica é expressa em minutos inteiros.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from domain.planning.enums import (
    DecisionType,
    DurationSource,
    MaterialStatus,
    ProposalStatus,
    SolutionStatus,
    UnscheduledReason,
    ViolationSeverity,
)

PositiveMinutes = Annotated[int, Field(gt=0)]
NonNegativeMinutes = Annotated[int, Field(ge=0)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone")
    return value


class TimeWindow(ContractModel):
    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        return _ensure_aware(value)

    @model_validator(mode="after")
    def ordered(self) -> TimeWindow:
        if self.end <= self.start:
            raise ValueError("window end must be after start")
        return self

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


class MaterialRequirement(ContractModel):
    item_id: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    reserved_quantity: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def reservation_cannot_exceed_requirement(self) -> MaterialRequirement:
        if self.reserved_quantity > self.quantity:
            raise ValueError("reserved quantity cannot exceed required quantity")
        return self


class InventoryPosition(ContractModel):
    item_id: str = Field(min_length=1)
    on_hand_quantity: float = Field(ge=0)
    reserved_quantity: float = Field(default=0, ge=0)
    lead_time_days: int | None = Field(default=None, ge=0)
    expected_inbound_at: datetime | None = None

    @field_validator("expected_inbound_at")
    @classmethod
    def inbound_timezone_required(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _ensure_aware(value)

    @property
    def net_available_quantity(self) -> float:
        return max(0.0, self.on_hand_quantity - self.reserved_quantity)


class WorkOrderOperation(ContractModel):
    work_order_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    title: str = ""
    status: str
    planning_status: str = ""
    created_at: datetime
    due_at: datetime | None = None
    priority_level: int | None = Field(default=None, ge=1, le=4)
    criticality: int | None = Field(default=None, ge=0, le=100)
    asset_id: str | None = None
    location_id: str | None = None
    activity_type_id: str | None = None
    planned_team_id: str | None = None
    planned_duration_minutes: PositiveMinutes | None = None
    required_worker_count: int = Field(default=1, ge=1, le=20)
    required_materials: tuple[MaterialRequirement, ...] = ()
    operational_windows: tuple[TimeWindow, ...] = ()
    blocked: bool = False
    block_reason: str | None = None

    @field_validator("created_at", "due_at")
    @classmethod
    def dates_require_timezone(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _ensure_aware(value)


class HistoricalExecution(ContractModel):
    work_order_id: str
    operation_id: str
    title: str = ""
    finished_at: datetime
    duration_minutes: PositiveMinutes
    labor_minutes: PositiveMinutes | None = None
    worker_ids: tuple[str, ...] = ()
    asset_id: str | None = None
    location_id: str | None = None
    activity_type_id: str | None = None
    team_id: str | None = None

    @field_validator("finished_at")
    @classmethod
    def finished_timezone_required(cls, value: datetime) -> datetime:
        return _ensure_aware(value)


class WorkerProfile(ContractModel):
    worker_id: str = Field(min_length=1)
    team_ids: tuple[str, ...] = ()
    qualification_ids: tuple[str, ...] = ()
    active: bool = True


class AvailabilitySlot(ContractModel):
    worker_id: str
    window: TimeWindow


class ExistingAssignment(ContractModel):
    operation_id: str
    worker_id: str
    window: TimeWindow


class PlanningSnapshot(ContractModel):
    schema_version: str = "1.0"
    snapshot_id: str
    tenant_id: str
    as_of: datetime
    operations: tuple[WorkOrderOperation, ...]
    history: tuple[HistoricalExecution, ...] = ()
    inventory: tuple[InventoryPosition, ...] = ()
    workers: tuple[WorkerProfile, ...] = ()
    availability: tuple[AvailabilitySlot, ...] = ()
    existing_assignments: tuple[ExistingAssignment, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("as_of")
    @classmethod
    def as_of_timezone_required(cls, value: datetime) -> datetime:
        return _ensure_aware(value)

    @model_validator(mode="after")
    def unique_operations(self) -> PlanningSnapshot:
        ids = [operation.operation_id for operation in self.operations]
        if len(ids) != len(set(ids)):
            raise ValueError("operation_id must be unique inside a snapshot")
        return self


class PlanningRequest(ContractModel):
    tenant_id: str
    period: TimeWindow
    as_of: datetime
    ruleset_version: str = "1"
    weights_version: str = "1"
    dry_run: bool = True
    max_repair_attempts: int = Field(default=1, ge=0, le=3)

    @field_validator("as_of")
    @classmethod
    def request_as_of_timezone_required(cls, value: datetime) -> datetime:
        return _ensure_aware(value)


class ScoreComponent(ContractModel):
    name: str
    raw_value: float
    normalized_value: float = Field(ge=0, le=100)
    weight: float = Field(ge=0)
    contribution: float = Field(ge=0)


class PriorityAssessment(ContractModel):
    operation_id: str
    score: float = Field(ge=0, le=100)
    band: str
    model: str
    components: tuple[ScoreComponent, ...]
    reason_codes: tuple[str, ...]
    missing_fields: tuple[str, ...] = ()


class DurationEstimate(ContractModel):
    operation_id: str
    minutes: PositiveMinutes | None
    p50_minutes: PositiveMinutes | None
    p80_minutes: PositiveMinutes | None
    source: DurationSource
    sample_size: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    reason_codes: tuple[str, ...]


class MaterialLineAssessment(ContractModel):
    item_id: str
    required_quantity: float = Field(gt=0)
    available_quantity: float | None = Field(default=None, ge=0)
    reserved_for_operation: float = Field(default=0, ge=0)
    missing_quantity: float | None = Field(default=None, ge=0)
    lead_time_days: int | None = Field(default=None, ge=0)
    blocking: bool
    reason_code: str


class MaterialAssessment(ContractModel):
    operation_id: str
    status: MaterialStatus
    blocking: bool
    lines: tuple[MaterialLineAssessment, ...] = ()
    reason_codes: tuple[str, ...]


class CapacitySlot(ContractModel):
    worker_id: str
    window: TimeWindow


class CapacityAssessment(ContractModel):
    worker_id: str
    gross_minutes: NonNegativeMinutes
    committed_minutes: NonNegativeMinutes
    net_minutes: NonNegativeMinutes
    slots: tuple[CapacitySlot, ...]


class ExecutorCandidate(ContractModel):
    operation_id: str
    worker_id: str
    score: float = Field(ge=0, le=100)
    eligible: bool
    available_minutes: NonNegativeMinutes
    reason_codes: tuple[str, ...]


class EnrichedOperation(ContractModel):
    operation: WorkOrderOperation
    priority: PriorityAssessment
    duration: DurationEstimate
    materials: MaterialAssessment
    executants: tuple[ExecutorCandidate, ...]


class PlanningStageTrace(ContractModel):
    sequence: int = Field(ge=1)
    stage: str = Field(min_length=1)
    elapsed_ms: float = Field(ge=0)
    counts: dict[str, Annotated[int, Field(ge=0)]] = Field(default_factory=dict)


class ScheduleAssignment(ContractModel):
    work_order_id: str
    operation_id: str
    worker_ids: tuple[str, ...]
    window: TimeWindow
    priority_score: float = Field(ge=0, le=100)
    reason_codes: tuple[str, ...]


class UnscheduledOperation(ContractModel):
    work_order_id: str
    operation_id: str
    reason: UnscheduledReason
    details: tuple[str, ...] = ()


class SchedulingSolution(ContractModel):
    status: SolutionStatus
    assignments: tuple[ScheduleAssignment, ...]
    unscheduled: tuple[UnscheduledOperation, ...]
    objective_value: float
    algorithm_version: str


class VerificationViolation(ContractModel):
    code: str
    severity: ViolationSeverity
    operation_id: str | None = None
    worker_id: str | None = None
    details: str
    repairable: bool = False


class VerificationReport(ContractModel):
    valid: bool
    input_hash: str
    violations: tuple[VerificationViolation, ...]


class HumanDecision(ContractModel):
    proposal_id: str
    decision: DecisionType
    decided_by: str = Field(min_length=1)
    decided_at: datetime
    reason: str = Field(min_length=1)

    @field_validator("decided_at")
    @classmethod
    def decision_timezone_required(cls, value: datetime) -> datetime:
        return _ensure_aware(value)


class ScheduleProposal(ContractModel):
    schema_version: str = "1.0"
    proposal_id: str
    tenant_id: str
    snapshot_id: str
    created_at: datetime
    period: TimeWindow
    status: ProposalStatus
    solution: SchedulingSolution
    verification: VerificationReport
    ruleset_version: str
    weights_version: str
    skill_versions: dict[str, str] = Field(default_factory=dict)
    decision: HumanDecision | None = None

    @field_validator("created_at")
    @classmethod
    def created_timezone_required(cls, value: datetime) -> datetime:
        return _ensure_aware(value)


class PlanningRunResult(ContractModel):
    proposal: ScheduleProposal
    priorities: tuple[PriorityAssessment, ...]
    durations: tuple[DurationEstimate, ...]
    materials: tuple[MaterialAssessment, ...]
    capacities: tuple[CapacityAssessment, ...]
    enriched: tuple[EnrichedOperation, ...]
    trace_events: tuple[PlanningStageTrace, ...] = ()
