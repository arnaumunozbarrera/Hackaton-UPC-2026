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
        """Accept legacy frontend field names for initial conditions.

        @param data: Raw request payload before Pydantic field parsing.
        @return: Payload with canonical snake_case keys.
        """
        payload = dict(data)
        if "temperatureC" in payload and "temperature_c" not in payload:
            payload["temperature_c"] = payload["temperatureC"]
        if "operationalLoad" in payload and "operational_load" not in payload:
            payload["operational_load"] = payload["operationalLoad"]
        if "maintenanceLevel" in payload and "maintenance_level" not in payload:
            payload["maintenance_level"] = payload["maintenanceLevel"]
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
        """Accept legacy simulation-run field names from older clients.

        @param data: Raw request payload before Pydantic field parsing.
        @return: Payload with canonical snake_case keys.
        """
        payload = dict(data)
        if "runId" in payload and "run_id" not in payload:
            payload["run_id"] = payload["runId"]
        if "scenarioId" in payload and "scenario_id" not in payload:
            payload["scenario_id"] = payload["scenarioId"]
        if "totalUsages" in payload and "total_usages" not in payload:
            payload["total_usages"] = payload["totalUsages"]
        if "usageStep" in payload and "usage_step" not in payload:
            payload["usage_step"] = payload["usageStep"]
        if "initialConditions" in payload and "initial_conditions" not in payload:
            payload["initial_conditions"] = payload["initialConditions"]
        if "selectedComponent" in payload and "selected_component" not in payload:
            payload["selected_component"] = payload["selectedComponent"]
        if "selectedComponentId" in payload and "selected_component" not in payload:
            payload["selected_component"] = payload["selectedComponentId"]
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
        """Accept legacy single-step field names and nested driver aliases.

        @param data: Raw request payload before Pydantic field parsing.
        @return: Payload with canonical snake_case keys.
        """
        payload = dict(data)
        if "runId" in payload and "run_id" not in payload:
            payload["run_id"] = payload["runId"]
        if "stepIndex" in payload and "step_index" not in payload:
            payload["step_index"] = payload["stepIndex"]
        if "usageCount" in payload and "usage_count" not in payload:
            payload["usage_count"] = payload["usageCount"]
        if "previousModelOutput" in payload and "previous_model_output" not in payload:
            payload["previous_model_output"] = payload["previousModelOutput"]
        drivers = payload.get("drivers")
        if isinstance(drivers, dict):
            normalized_drivers = dict(drivers)
            if "temperatureC" in normalized_drivers and "temperature_c" not in normalized_drivers:
                normalized_drivers["temperature_c"] = normalized_drivers["temperatureC"]
            if "operationalLoad" in normalized_drivers and "operational_load" not in normalized_drivers:
                normalized_drivers["operational_load"] = normalized_drivers["operationalLoad"]
            if "maintenanceLevel" in normalized_drivers and "maintenance_level" not in normalized_drivers:
                normalized_drivers["maintenance_level"] = normalized_drivers["maintenanceLevel"]
            payload["drivers"] = normalized_drivers
        if "t_h" in payload and "usage_count" not in payload:
            payload["usage_count"] = payload["t_h"]
        return payload


class PredictionRequest(BaseModel):
    run_id: str
    component_id: str

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, data: dict) -> dict:
        """Accept legacy prediction field names from older clients.

        @param data: Raw request payload before Pydantic field parsing.
        @return: Payload with canonical snake_case keys.
        """
        payload = dict(data)
        if "runId" in payload and "run_id" not in payload:
            payload["run_id"] = payload["runId"]
        if "componentId" in payload and "component_id" not in payload:
            payload["component_id"] = payload["componentId"]
        if "selectedComponent" in payload and "component_id" not in payload:
            payload["component_id"] = payload["selectedComponent"]
        return payload


class ChatQueryRequest(BaseModel):
    run_id: str | None = None
    component_id: str | None = None
    question: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, data: dict) -> dict:
        """Accept legacy chat field names from older clients.

        @param data: Raw request payload before Pydantic field parsing.
        @return: Payload with canonical snake_case keys.
        """
        payload = dict(data)
        if "runId" in payload and "run_id" not in payload:
            payload["run_id"] = payload["runId"]
        if "componentId" in payload and "component_id" not in payload:
            payload["component_id"] = payload["componentId"]
        return payload

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
    provider: str = "ollama"
    model: str | None = None
    mode: str = "rewrite"
