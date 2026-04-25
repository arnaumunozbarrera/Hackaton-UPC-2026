"""Phase 2 simulation runner."""

from __future__ import annotations

import math
import random
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from app.adapters.phase1_adapter import adapt_phase1_output, get_dependencies_for_component
from app.core.phase1 import load_phase1_config, run_phase1_update, to_phase1_drivers
from app.messages.message_generator import generate_messages
from app.prediction.predictor import predict_component_failure_from_timeline
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

    short_wave = math.sin(step_index / 3.0)
    long_wave = math.sin(step_index / 11.0 + 0.8)
    process_noise = rng.uniform(-1.0, 1.0)
    shock = 0.0

    if rng.random() < 0.08 * stochasticity:
        shock = rng.uniform(0.35, 1.0) * stochasticity

    adjusted = dict(phase1_drivers)
    load_multiplier = (
        1.0
        + 0.22 * short_wave * stochasticity
        + 0.18 * long_wave * stochasticity
        + 0.28 * process_noise * stochasticity
        + 1.15 * shock
    )
    temperature_stress = (
        phase1_drivers["temperature_stress"]
        + 0.14 * short_wave * stochasticity
        + 0.08 * long_wave * stochasticity
        + 0.16 * process_noise * stochasticity
        + 0.45 * shock
    )

    adjusted["temperature_stress"] = max(0.0, min(temperature_stress, 1.0))
    temperature_direction = 1.0 if phase1_drivers["temperature_c"] >= 35.0 else -1.0
    adjusted["temperature_c"] = 35.0 + temperature_direction * (
        20.0 * adjusted["temperature_stress"]
    )
    adjusted["humidity"] = max(
        0.0,
        min(
            phase1_drivers["humidity"]
            + 0.07 * long_wave * stochasticity
            + 0.04 * process_noise * stochasticity,
            1.0,
        ),
    )
    adjusted["contamination"] = max(
        0.0,
        min(
            phase1_drivers["contamination"]
            + 0.08 * process_noise * stochasticity
            + 0.22 * shock,
            1.0,
        ),
    )
    adjusted["operational_load"] = max(
        0.0,
        phase1_drivers["operational_load"] * max(0.15, load_multiplier),
    )
    adjusted["maintenance_level"] = max(0.0, min(phase1_drivers["maintenance_level"], 1.0))
    return adjusted


def _build_usage_counts(total_usages: float, usage_step: float) -> list[float]:
    usage_counts = [0.0]
    current_usage = usage_step
    epsilon = 1e-9

    while current_usage < total_usages - epsilon:
        usage_counts.append(round(current_usage, 6))
        current_usage += usage_step

    if abs(usage_counts[-1] - total_usages) > epsilon:
        usage_counts.append(round(total_usages, 6))

    return usage_counts


def _build_initial_phase1_output(
    initial_conditions: dict,
    phase1_config: dict,
) -> tuple[dict, dict]:
    initial_drivers = to_phase1_drivers(initial_conditions)
    no_load_drivers = dict(initial_drivers)
    no_load_drivers["operational_load"] = 0.0
    return (
        run_phase1_update(previous_state={}, drivers=no_load_drivers, config=phase1_config),
        no_load_drivers,
    )


def _scale_drivers_for_usage_delta(drivers: dict, usage_delta: float) -> dict:
    if math.isclose(usage_delta, 1.0):
        return drivers

    scaled_drivers = dict(drivers)
    scaled_drivers["operational_load"] = max(
        0.0,
        scaled_drivers["operational_load"] * usage_delta,
    )
    return scaled_drivers


def _advance_phase1_to_usage(
    previous_state: dict,
    current_usage: float,
    target_usage: float,
    initial_conditions: dict,
    rng: random.Random,
    phase1_config: dict,
) -> tuple[dict, dict]:
    state = previous_state
    last_drivers = to_phase1_drivers(initial_conditions)
    epsilon = 1e-9

    while current_usage < target_usage - epsilon:
        next_boundary = math.floor(current_usage + epsilon) + 1.0
        usage_delta = min(next_boundary - current_usage, target_usage - current_usage)
        driver_index = int(max(1.0, math.ceil(current_usage + epsilon)))
        drivers = _generate_drivers_for_step(initial_conditions, driver_index, rng)
        last_drivers = _scale_drivers_for_usage_delta(drivers, usage_delta)
        state = run_phase1_update(previous_state=state, drivers=last_drivers, config=phase1_config)
        current_usage = round(current_usage + usage_delta, 10)

    return state, last_drivers


def _driver_snapshot(drivers: dict) -> dict:
    return {
        "operational_load": round(drivers["operational_load"], 4),
        "contamination": round(drivers["contamination"], 4),
        "humidity": round(drivers["humidity"], 4),
        "temperature_stress": round(drivers["temperature_stress"], 4),
        "maintenance_level": round(drivers["maintenance_level"], 4),
    }


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
    usage_counts = _build_usage_counts(total_usages, usage_step)
    base_timestamp = datetime.now(timezone.utc)
    rng = random.Random(config.get("seed", 1234))
    previous_internal_output, point_drivers = _build_initial_phase1_output(
        config["initial_conditions"],
        phase1_config,
    )
    current_usage = 0.0
    timeline = []
    persisted_steps = []

    for step_index, usage_count in enumerate(usage_counts):
        if step_index == 0:
            phase1_output = previous_internal_output
        else:
            phase1_output, point_drivers = _advance_phase1_to_usage(
                previous_state=previous_internal_output,
                current_usage=current_usage,
                target_usage=usage_count,
                initial_conditions=config["initial_conditions"],
                rng=rng,
                phase1_config=phase1_config,
            )
        adapted_output = adapt_phase1_output(phase1_output)
        point = {
            "run_id": run_id,
            "scenario_id": scenario_id,
            "step_index": step_index,
            "usage_count": usage_count,
            "timestamp": _to_iso8601(base_timestamp + timedelta(minutes=usage_count)),
            "drivers": _driver_snapshot(point_drivers),
            "model_output": adapted_output,
        }
        persisted_steps.append(
            {
                "run_id": run_id,
                "scenario_id": scenario_id,
                "step_index": step_index,
                "usage_count": usage_count,
                "timestamp": point["timestamp"],
                "drivers": point["drivers"],
                "phase1_output": phase1_output,
            }
        )
        timeline.append(point)
        previous_internal_output = phase1_output
        current_usage = usage_count

    historian.save_simulation_steps(persisted_steps)
    prediction = predict_component_failure_from_timeline(
        run_id,
        selected_component,
        timeline,
    )
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
