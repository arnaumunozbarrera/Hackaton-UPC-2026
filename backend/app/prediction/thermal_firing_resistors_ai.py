"""Scikit-learn AI predictor for the thermal firing resistors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from time import perf_counter

from app.core.phase1 import load_phase1_config
from app.prediction.artifact_store import load_model_artifact
from app.prediction.ai_curve_utils import calibrate_ai_health
from model_mathematic.thermal_firing_resistors import (
    calculate_thermal_firing_resistors_state,
)
from sklearn.ensemble import HistGradientBoostingRegressor


COMPONENT_ID = "thermal_firing_resistors"
PREVENTIVE_FAILURE_THRESHOLD = 0.15
MODEL_RANDOM_STATE = 2026
SYNTHETIC_LABEL_SCALE = 1.0

FEATURE_NAMES = (
    "previous_health",
    "operational_load",
    "contamination",
    "humidity",
    "temperature_stress",
    "maintenance_level",
    "heating_elements_health",
    "effective_temperature_stress",
    "resistance_ohm",
    "firing_energy_factor",
    "pulse_uniformity",
    "misfire_risk",
    "effective_load",
    "previous_damage_per_usage",
    "usage_count",
)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(float(value), maximum))


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _to_iso8601(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _component_health(component: dict) -> float:
    return float(component.get("health_index", component.get("health", 1.0)))


def _status_from_health(health: float) -> str:
    if health <= PREVENTIVE_FAILURE_THRESHOLD:
        return "FAILED"
    if health <= 0.4:
        return "CRITICAL"
    if health <= 0.7:
        return "DEGRADED"
    return "FUNCTIONAL"


def _heating_health_from_point(point: dict) -> float:
    components = point.get("components", {})
    heating_state = components.get("heating_elements")
    if heating_state is not None:
        return _component_health(heating_state)
    resistor_metrics = components.get(COMPONENT_ID, {}).get("metrics", {})
    return float(resistor_metrics.get("heating_elements_health", 1.0))


def _metrics_from_state(
    config: dict,
    health: float,
    drivers: dict,
    heating_elements_health: float,
) -> dict:
    state = calculate_thermal_firing_resistors_state(
        previous_state={"health": health},
        drivers=drivers,
        config=config,
        heating_elements_state={"health": heating_elements_health},
    )
    return state["metrics"]


def _feature_row(
    previous_health: float,
    operational_load: float,
    contamination: float,
    humidity: float,
    temperature_stress: float,
    maintenance_level: float,
    heating_elements_health: float,
    effective_temperature_stress: float,
    resistance_ohm: float,
    firing_energy_factor: float,
    pulse_uniformity: float,
    misfire_risk: float,
    effective_load: float,
    previous_damage_per_usage: float,
    usage_count: float,
) -> list[float]:
    return [
        float(previous_health),
        float(operational_load),
        float(contamination),
        float(humidity),
        float(temperature_stress),
        float(maintenance_level),
        float(heating_elements_health),
        float(effective_temperature_stress),
        float(resistance_ohm),
        float(firing_energy_factor),
        float(pulse_uniformity),
        float(misfire_risk),
        float(effective_load),
        float(previous_damage_per_usage),
        float(usage_count),
    ]


def _synthetic_label_multiplier(
    usage_count: float,
    contamination: float,
    humidity: float,
    temperature_stress: float,
    maintenance_level: float,
    heating_elements_health: float,
    previous_health: float,
) -> float:
    heating_degradation = 1.0 - heating_elements_health
    thermal_stress = temperature_stress + 0.25 * heating_degradation
    deposit_stress = contamination * (0.6 + 0.4 * humidity)
    degradation = 1.0 - previous_health
    misfire_pressure = degradation * (0.5 + 0.5 * thermal_stress)
    multiplier = (
        1.0
        + 0.10 * thermal_stress
        + 0.07 * deposit_stress
        + 0.06 * misfire_pressure
        + 0.04 * humidity
        - 0.05 * maintenance_level
    )
    return _clamp(multiplier, 0.9, 1.24)


def _build_training_dataset(config: dict) -> tuple[list[list[float]], list[float]]:
    health_values = (0.16, 0.28, 0.45, 0.62, 0.8, 1.0)
    load_values = (0.2, 0.72, 1.2, 1.8)
    contamination_values = (0.0, 0.35, 0.7, 1.0)
    humidity_values = (0.0, 0.5, 1.0)
    temperature_values = (0.0, 0.35, 0.7, 1.0)
    maintenance_values = (0.0, 0.55, 1.0)
    heating_health_values = (0.35, 0.7, 1.0)
    usage_values = (0.0, 1200.0, 2400.0)

    rows = []
    targets = []
    for health in health_values:
        for heating_elements_health in heating_health_values:
            for operational_load in load_values:
                for contamination in contamination_values:
                    for humidity in humidity_values:
                        for temperature_stress in temperature_values:
                            for maintenance_level in maintenance_values:
                                drivers = {
                                    "operational_load": operational_load,
                                    "contamination": contamination,
                                    "humidity": humidity,
                                    "temperature_stress": temperature_stress,
                                    "maintenance_level": maintenance_level,
                                }
                                next_state = (
                                    calculate_thermal_firing_resistors_state(
                                        previous_state={"health": health},
                                        drivers=drivers,
                                        config=config,
                                        heating_elements_state={
                                            "health": heating_elements_health
                                        },
                                    )
                                )
                                metrics = next_state["metrics"]
                                mathematical_damage = float(
                                    next_state["damage"]["total"]
                                )
                                for usage_count in usage_values:
                                    multiplier = _synthetic_label_multiplier(
                                        usage_count,
                                        contamination,
                                        humidity,
                                        temperature_stress,
                                        maintenance_level,
                                        heating_elements_health,
                                        health,
                                    )
                                    rows.append(
                                        _feature_row(
                                            previous_health=health,
                                            operational_load=operational_load,
                                            contamination=contamination,
                                            humidity=humidity,
                                            temperature_stress=temperature_stress,
                                            maintenance_level=maintenance_level,
                                            heating_elements_health=heating_elements_health,
                                            effective_temperature_stress=float(
                                                metrics[
                                                    "effective_temperature_stress"
                                                ]
                                            ),
                                            resistance_ohm=float(
                                                metrics["resistance_ohm"]
                                            ),
                                            firing_energy_factor=float(
                                                metrics["firing_energy_factor"]
                                            ),
                                            pulse_uniformity=float(
                                                metrics["pulse_uniformity"]
                                            ),
                                            misfire_risk=float(
                                                metrics["misfire_risk"]
                                            ),
                                            effective_load=float(
                                                metrics["effective_load"]
                                            ),
                                            previous_damage_per_usage=0.0,
                                            usage_count=usage_count,
                                        )
                                    )
                                    targets.append(
                                        mathematical_damage
                                        * multiplier
                                        * SYNTHETIC_LABEL_SCALE
                                    )

    return rows, targets


def train_thermal_firing_resistors_model() -> tuple[HistGradientBoostingRegressor, dict]:
    started_at = perf_counter()
    config = load_phase1_config()
    rows, targets = _build_training_dataset(config)
    model = HistGradientBoostingRegressor(
        max_iter=130,
        max_leaf_nodes=31,
        learning_rate=0.08,
        l2_regularization=0.01,
        random_state=MODEL_RANDOM_STATE,
    )
    model.fit(rows, targets)
    return model, {
        "training_samples": len(rows),
        "feature_names": list(FEATURE_NAMES),
        "training_seconds": round(perf_counter() - started_at, 3),
        "model": "HistGradientBoostingRegressor",
        "random_state": MODEL_RANDOM_STATE,
        "synthetic_label_scale": SYNTHETIC_LABEL_SCALE,
        "trained_from_scratch": True,
    }


def _build_ai_curve(
    timeline: list[dict],
    model: HistGradientBoostingRegressor,
    config: dict,
) -> list[dict]:
    first_point = timeline[0]
    first_component = first_point["components"][COMPONENT_ID]
    ai_health = _component_health(first_component)
    previous_usage = float(first_point["usage_count"])
    previous_damage_per_usage = 0.0
    curve = [
        {
            "usage_count": round(previous_usage, 2),
            "health": round(ai_health, 6),
            "status": _status_from_health(ai_health),
        }
    ]

    for point in timeline[1:]:
        usage_count = float(point["usage_count"])
        usage_delta = max(usage_count - previous_usage, 0.0)
        drivers = point["drivers"]
        heating_elements_health = _heating_health_from_point(point)
        metrics = _metrics_from_state(
            config,
            ai_health,
            drivers,
            heating_elements_health,
        )
        features = _feature_row(
            previous_health=ai_health,
            operational_load=float(drivers["operational_load"]),
            contamination=float(drivers["contamination"]),
            humidity=float(drivers["humidity"]),
            temperature_stress=float(drivers["temperature_stress"]),
            maintenance_level=float(drivers["maintenance_level"]),
            heating_elements_health=heating_elements_health,
            effective_temperature_stress=float(
                metrics["effective_temperature_stress"]
            ),
            resistance_ohm=float(metrics["resistance_ohm"]),
            firing_energy_factor=float(metrics["firing_energy_factor"]),
            pulse_uniformity=float(metrics["pulse_uniformity"]),
            misfire_risk=float(metrics["misfire_risk"]),
            effective_load=float(metrics["effective_load"]),
            previous_damage_per_usage=previous_damage_per_usage,
            usage_count=usage_count,
        )
        damage_per_usage = max(float(model.predict([features])[0]), 0.0)
        damage = damage_per_usage * usage_delta
        predicted_health = _clamp(ai_health - damage, 0.0, 1.0)
        ai_health = calibrate_ai_health(
            predicted_health=predicted_health,
            previous_health=ai_health,
        )
        previous_damage_per_usage = damage_per_usage
        previous_usage = usage_count
        curve.append(
            {
                "usage_count": round(usage_count, 2),
                "health": round(ai_health, 6),
                "status": _status_from_health(ai_health),
            }
        )

    return curve


def _first_failure_point(curve: list[dict]) -> dict | None:
    for point in curve:
        if point["health"] <= PREVENTIVE_FAILURE_THRESHOLD:
            return point
    return None


def predict_thermal_firing_resistors_ai_from_timeline(
    run_id: str,
    timeline: list[dict],
) -> dict:
    points = [
        point
        for point in timeline
        if COMPONENT_ID in point.get("components", {})
    ]
    if len(points) < 2:
        return {
            "run_id": run_id,
            "component_id": COMPONENT_ID,
            "confidence": 0.2,
            "model_family": "thermal_firing_resistors_sklearn_gradient_boosting",
            "prediction_method": "supervised_synthetic_gradient_boosting",
            "reason": "Not enough thermal firing resistor history for the AI predictor.",
        }

    config = load_phase1_config()
    artifact = load_model_artifact(COMPONENT_ID)
    model = artifact["model"]
    training = artifact["training"]
    curve = _build_ai_curve(points, model, config)
    failure_point = _first_failure_point(curve)
    last_point = points[-1]
    last_component = last_point["components"][COMPONENT_ID]
    last_timestamp = _parse_timestamp(last_point["timestamp"])

    if failure_point is None:
        predicted_failure_usage = None
        predicted_failure_timestamp = None
        usages_until_failure = None
    else:
        predicted_failure_usage = failure_point["usage_count"]
        usages_until_failure = max(
            predicted_failure_usage - float(last_point["usage_count"]),
            0.0,
        )
        predicted_failure_timestamp = _to_iso8601(
            last_timestamp + timedelta(minutes=usages_until_failure)
        )

    confidence = 0.62 + min(len(points) / 750.0, 0.17)
    if failure_point is not None:
        confidence += 0.07

    return {
        "run_id": run_id,
        "component_id": COMPONENT_ID,
        "predicted_failure_timestamp": predicted_failure_timestamp,
        "predicted_failure_usage": predicted_failure_usage,
        "confidence": round(_clamp(confidence, 0.2, 0.9), 2),
        "model_family": "thermal_firing_resistors_sklearn_gradient_boosting",
        "prediction_method": "supervised_synthetic_gradient_boosting",
        "horizon": {
            "threshold": PREVENTIVE_FAILURE_THRESHOLD,
            "usages_until_failure": usages_until_failure,
        },
        "ai_prediction_curve": curve,
        "training": training,
        "evidence": {
            "run_id": run_id,
            "timestamp": last_point["timestamp"],
            "usage_count": float(last_point["usage_count"]),
            "health": _component_health(last_component),
            "status": last_component["status"],
        },
        "explanation": {
            "target": "damage_per_usage",
            "feature_names": list(FEATURE_NAMES),
            "top_factors": [
                {"name": "effective_temperature_stress", "direction": "risk"},
                {"name": "heating_elements_health", "direction": "risk"},
                {"name": "contamination", "direction": "risk"},
                {"name": "pulse_uniformity", "direction": "state"},
                {"name": "maintenance_level", "direction": "protective"},
            ],
        },
    }
