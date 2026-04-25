"""Phase 2 simulation runner."""

from __future__ import annotations

import math
import random
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from app.adapters.phase1_adapter import adapt_phase1_output, get_dependencies_for_component
from app.core.phase1 import load_phase1_config, run_phase1_update, to_phase1_drivers
from app.messages.message_generator import generate_messages
from app.prediction.predictor import predict_component_failure
from app.storage import historian


def _to_iso8601(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_config(config: dict) -> dict:
    normalized = deepcopy(config)
    normalized.setdefault("seed", 1234)
    normalized.setdefault("selected_component", "heating_elements")
    normalized.setdefault("scenario_id", "baseline")
    normalized.setdefault("description", None)
    initial_conditions = normalized.setdefault("initial_conditions", {})
    initial_conditions.setdefault("temperature_c", 42)
    initial_conditions.setdefault("humidity", 0.38)
    initial_conditions.setdefault("contamination", 0.31)
    initial_conditions.setdefault("operational_load", 0.72)
    initial_conditions.setdefault("maintenance_level", 0.64)
    initial_conditions.setdefault("stochasticity", 0.45)
    return normalized


def _generate_drivers_for_step(initial_conditions: dict, step_index: int, rng: random.Random) -> dict:
    phase1_drivers = to_phase1_drivers(initial_conditions)
    stochasticity = max(0.0, min(float(initial_conditions.get("stochasticity", 0.0)), 1.0))

    if step_index == 0 or stochasticity == 0:
        return phase1_drivers

    wave = math.sin(step_index / 3.0)
    noise = rng.uniform(-1.0, 1.0) * stochasticity

    adjusted = dict(phase1_drivers)
    adjusted["temperature_c"] = phase1_drivers["temperature_c"] + 1.8 * wave * stochasticity + 1.2 * noise
    adjusted["temperature_stress"] = max(0.0, min(phase1_drivers["temperature_stress"] + 0.07 * wave * stochasticity + 0.05 * noise, 1.0))
    adjusted["humidity"] = max(0.0, min(phase1_drivers["humidity"] + 0.03 * wave * stochasticity, 1.0))
    adjusted["contamination"] = max(0.0, min(phase1_drivers["contamination"] + 0.04 * noise, 1.0))
    adjusted["operational_load"] = max(0.0, phase1_drivers["operational_load"] + 0.05 * wave * stochasticity)
    adjusted["maintenance_level"] = max(0.0, min(phase1_drivers["maintenance_level"], 1.0))
    return adjusted


def run_simulation(config: dict) -> dict:
    config = _normalize_config(config)
    run_id = config["run_id"]
    scenario_id = config["scenario_id"]
    selected_component = config["selected_component"]
    total_usages = float(config["total_usages"])
    usage_step = float(config["usage_step"])
    created_at = _to_iso8601(datetime.now(timezone.utc))

    historian.create_run(
        run_id=run_id,
        scenario_id=scenario_id,
        created_at=created_at,
        description=config.get("description"),
        selected_component=selected_component,
        total_usages=total_usages,
        usage_step=usage_step,
        config=config,
    )

    phase1_config = load_phase1_config()
    step_count = int(round(total_usages / usage_step))
    base_timestamp = datetime.now(timezone.utc)
    rng = random.Random(config.get("seed", 1234))
    previous_internal_output = {}
    timeline = []

    for step_index in range(step_count + 1):
        usage_count = round(step_index * usage_step, 6)
        drivers = _generate_drivers_for_step(config["initial_conditions"], step_index, rng)
        phase1_output = run_phase1_update(previous_state=previous_internal_output, drivers=drivers, config=phase1_config)
        adapted_output = adapt_phase1_output(phase1_output)
        point = {
            "run_id": run_id,
            "scenario_id": scenario_id,
            "step_index": step_index,
            "usage_count": usage_count,
            "timestamp": _to_iso8601(base_timestamp + timedelta(minutes=step_index)),
            "drivers": {
                "operational_load": round(drivers["operational_load"], 4),
                "contamination": round(drivers["contamination"], 4),
                "humidity": round(drivers["humidity"], 4),
                "temperature_stress": round(drivers["temperature_stress"], 4),
                "maintenance_level": round(drivers["maintenance_level"], 4),
            },
            "model_output": adapted_output,
        }
        historian.save_simulation_step(
            run_id=run_id,
            scenario_id=scenario_id,
            step_index=step_index,
            timestamp=point["timestamp"],
            drivers=point["drivers"],
            phase1_output=phase1_output,
        )
        timeline.append(point)
        previous_internal_output = phase1_output

    prediction = predict_component_failure(run_id, selected_component)
    historian.save_prediction(run_id, selected_component, created_at, prediction)

    messages = generate_messages(run_id, timeline)
    historian.save_messages(run_id, messages)

    return {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "selected_component": selected_component,
        "timeline": timeline,
        "prediction": prediction,
        "messages": messages,
        "dependencies": get_dependencies_for_component(selected_component),
    }


def run_single_step(payload: dict) -> dict:
    phase1_config = load_phase1_config()
    phase1_drivers = to_phase1_drivers(payload.get("drivers", {}))
    adapted_output = adapt_phase1_output(
        run_phase1_update(
            previous_state=payload.get("previous_model_output") or {},
            drivers=phase1_drivers,
            config=phase1_config,
        )
    )
    timestamp = payload.get("timestamp") or _to_iso8601(datetime.now(timezone.utc))
    return {
        "run_id": payload["run_id"],
        "step_index": payload["step_index"],
        "usage_count": payload["usage_count"],
        "timestamp": timestamp,
        "drivers": payload.get("drivers", {}),
        "model_output": adapted_output,
    }
