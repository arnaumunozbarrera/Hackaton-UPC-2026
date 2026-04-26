"""Phase 1 integration helpers."""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from model_mathematic.logic_engine import update_machine_state  # noqa: E402


CONFIG_PATH = REPO_ROOT / "config" / "model_parameters.yaml"
DEFAULT_SIMULATION_CONFIG = {
    "run_id": "run_default",
    "scenario_id": "baseline",
    "total_usages": 96,
    "usage_step": 4,
    "initial_conditions": {
        "temperature_c": 42,
        "humidity": 0.38,
        "contamination": 0.31,
        "operational_load": 0.72,
        "maintenance_level": 0.64,
        "stochasticity": 0.45,
    },
    "selected_component": "heating_elements",
    "seed": 1234,
}


def load_phase1_config() -> dict:
    """Load the YAML configuration consumed by the Phase 1 model engine.

    @return: Parsed Phase 1 configuration dictionary.
    """
    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def get_default_simulation_config() -> dict:
    return deepcopy(DEFAULT_SIMULATION_CONFIG)


def normalize_temperature_stress(temperature_c: float) -> float:
    """Convert an absolute chamber temperature into a normalized stress index.

    @param temperature_c: Chamber temperature in degrees Celsius.
    @return: Thermal stress normalized to the inclusive range from 0.0 to 1.0.
    """
    baseline_c = 35.0
    span_c = 20.0
    normalized = abs(float(temperature_c) - baseline_c) / span_c
    return max(0.0, min(normalized, 1.0))


def to_phase1_drivers(initial_conditions: dict) -> dict:
    """Translate API simulation inputs into the driver contract expected by Phase 1.

    @param initial_conditions: User-facing initial conditions from the API request.
    @return: Normalized driver dictionary used by the mathematical model.
    """
    temperature_c = float(initial_conditions.get("temperature_c", 35.0))
    maintenance_level = initial_conditions.get(
        "maintenance_level",
        initial_conditions.get("maintenance", 0.0),
    )
    return {
        "temperature_c": temperature_c,
        "temperature_stress": normalize_temperature_stress(temperature_c),
        "humidity": float(initial_conditions.get("humidity", 0.0)),
        "contamination": float(initial_conditions.get("contamination", 0.0)),
        "operational_load": float(initial_conditions.get("operational_load", 0.0)),
        "maintenance_level": float(maintenance_level),
        "stochasticity": float(initial_conditions.get("stochasticity", 0.0)),
    }


def run_phase1_update(previous_state: dict | None, drivers: dict, config: dict | None = None) -> dict:
    """Run one deterministic Phase 1 update with optional explicit configuration.

    @param previous_state: Previous Phase 1 state, or None for a fresh model update.
    @param drivers: Normalized operating drivers for the current update.
    @param config: Optional model configuration; the default YAML is loaded when omitted.
    @return: Raw Phase 1 machine state.
    """
    phase1_config = config or load_phase1_config()
    return update_machine_state(previous_state=previous_state or {}, drivers=drivers, config=phase1_config)
