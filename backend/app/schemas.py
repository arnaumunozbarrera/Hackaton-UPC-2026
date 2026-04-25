"""Request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InitialConditions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    temperature_c: float = 42
    humidity: float = 0.38
    contamination: float = 0.31
    operational_load: float = 0.72
    maintenance_level: float = 0.64
    stochasticity: float = 0.45

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, data: dict) -> dict:
        payload = dict(data)
        if "maintenance" in payload and "maintenance_level" not in payload:
            payload["maintenance_level"] = payload["maintenance"]
        return payload


class SimulationRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    total_usages: float = Field(gt=0)
    usage_step: float = Field(gt=0)
    initial_conditions: InitialConditions
    selected_component: str = Field(min_length=1)
    description: str | None = None
    seed: int | None = 1234

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, data: dict) -> dict:
        payload = dict(data)
        if "duration_h" in payload and "total_usages" not in payload:
            payload["total_usages"] = payload["duration_h"]
        if "step_h" in payload and "usage_step" not in payload:
            payload["usage_step"] = payload["step_h"]
        return payload

class SimulationStepRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    run_id: str
    step_index: int
    usage_count: float
    previous_model_output: dict = Field(default_factory=dict)
    drivers: dict = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, data: dict) -> dict:
        payload = dict(data)
        if "t_h" in payload and "usage_count" not in payload:
            payload["usage_count"] = payload["t_h"]
        return payload


class PredictionRequest(BaseModel):
    run_id: str
    component_id: str

class AgentAskRequest(BaseModel):
    question: str = Field(min_length=1)
    horizon_steps: int = Field(default=24, gt=0)
    history_window_steps: int | None = None
    include_analysis: bool = False

class AgentLLMContextRequest(BaseModel):
    question: str = Field(min_length=1)
    horizon_steps: int = Field(default=24, gt=0)
    history_window_steps: int | None = None
    max_alternatives_per_decision: int = Field(default=5, ge=1, le=10)

class AgentLLMAnswerRequest(BaseModel):
    question: str = Field(min_length=1)
    horizon_steps: int = Field(default=24, gt=0)
    history_window_steps: int | None = None
    max_alternatives_per_decision: int = Field(default=5, ge=1, le=10)
    include_context: bool = False
    provider: str = "mock"
    model: str | None = None
    mode: str = "rewrite"