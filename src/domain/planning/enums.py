"""Enumerações estáveis usadas nos contratos do planejador."""

from enum import StrEnum


class MaterialStatus(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
    NOT_REQUIRED = "not_required"


class DurationSource(StrEnum):
    PLANNED = "planned"
    SAME_ACTIVITY_AND_ASSET = "same_activity_and_asset"
    SAME_ACTIVITY_AND_LOCATION = "same_activity_and_location"
    SAME_ASSET = "same_asset"
    SAME_ACTIVITY = "same_activity"
    SAME_LOCATION = "same_location"
    SIMILAR_TITLE = "similar_title"
    GLOBAL_MEDIAN = "global_median"
    DEFAULT = "default"
    UNAVAILABLE = "unavailable"


class SolutionStatus(StrEnum):
    FEASIBLE = "feasible"
    PARTIAL = "partial"
    INFEASIBLE = "infeasible"


class ProposalStatus(StrEnum):
    DRAFT = "draft"
    INVALID = "invalid"
    APPROVED = "approved"
    REJECTED = "rejected"


class DecisionType(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class UnscheduledReason(StrEnum):
    BLOCKED = "blocked"
    MATERIAL = "material"
    DURATION = "duration"
    NO_EXECUTANT = "no_executant"
    NO_CAPACITY = "no_capacity"
    OUTSIDE_WINDOW = "outside_window"
    OUTSIDE_PERIOD = "outside_period"
    MANUAL = "manual"


class ViolationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
