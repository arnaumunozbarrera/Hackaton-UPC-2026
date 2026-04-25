from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    FAILED = "FAILED"


class ActionType(str, Enum):
    CONTINUE_OPERATION = "CONTINUE_OPERATION"
    REDUCE_LOAD = "REDUCE_LOAD"
    TRIGGER_COOLDOWN = "TRIGGER_COOLDOWN"
    RUN_CLEANING_CYCLE = "RUN_CLEANING_CYCLE"
    SCHEDULE_MAINTENANCE = "SCHEDULE_MAINTENANCE"
    REPLACE_COMPONENT = "REPLACE_COMPONENT"
    IMPROVE_ENVIRONMENT = "IMPROVE_ENVIRONMENT"
    STOP_MACHINE = "STOP_MACHINE"


@dataclass(frozen=True)
class Evidence:
    run_id: str
    timestamp: str
    component_id: str
    field: str
    value: Any


@dataclass(frozen=True)
class Diagnosis:
    issue: str
    component_id: str
    severity: Severity
    description: str
    evidence: list[Evidence]


@dataclass(frozen=True)
class Forecast:
    horizon_steps: int
    predicted_status: str
    time_to_critical_steps: int | None
    time_to_failure_steps: int | None
    risk_score: float


@dataclass(frozen=True)
class ActionEvaluation:
    action: ActionType
    projected_health_index: float
    predicted_status: str
    risk_score: float
    expected_effect: str


@dataclass(frozen=True)
class Recommendation:
    action: ActionType
    priority: Severity
    expected_effect: str
    evidence: list[Evidence]
    alternatives: list[ActionEvaluation] = field(default_factory=list)


@dataclass(frozen=True)
class AgentDecision:
    diagnosis: Diagnosis
    forecast: Forecast
    recommendation: Recommendation