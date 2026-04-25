"""Scikit-learn AI predictor for the recoater drive motor."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from time import perf_counter

from app.core.phase1 import load_phase1_config
from app.prediction.artifact_store import load_model_artifact
from app.prediction.ai_uncertainty import with_ai_uncertainty
from app.prediction.ai_curve_utils import calibrate_ai_health
from app.prediction.heuristic_teacher import (
    HEURISTIC_TEACHER_TYPE,
    HEURISTIC_TEACHER_VERSION,
    apply_hybrid_teacher,
)
from model_mathematic.recoater_drive_motor import calculate_recoater_drive_motor_state
from sklearn.ensemble import HistGradientBoostingRegressor


COMPONENT_ID = "recoater_drive_motor"
PREVENTIVE_FAILURE_THRESHOLD = 0.15
MODEL_RANDOM_STATE = 2026
SYNTHETIC_LABEL_SCALE = 1.0

FEATURE_NAMES = (
    "previous_health",
    "effective_age_cycles",
    "operational_load",
    "contamination",
    "humidity",
    "temperature_stress",
    "maintenance_level",
    "linear_guide_health",
    "torque_margin",
    "current_draw_factor",
    "vibration_index",
    "previous_damage_per_usage",
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


def _guide_health_from_point(point: dict) -> float:
    guide_state = point.get("components", {}).get("linear_guide")
    if guide_state is None:
        motor_metrics = point.get("components", {}).get(COMPONENT_ID, {}).get("metrics", {})
        return float(motor_metrics.get("linear_guide_health", 1.0))
    return _component_health(guide_state)


def _metrics_from_health(config: dict, health: float, guide_health: float) -> dict:
    state = calculate_recoater_drive_motor_state(
        previous_state={"health": health},
        drivers={
            "operational_load": 0.0,
            "contamination": 0.0,
            "humidity": 0.0,
            "temperature_stress": 0.0,
            "maintenance_level": 0.0,
        },
        config=config,
        linear_guide_state={"health": guide_health},
    )
    return state["metrics"]


def _feature_row(
    previous_health: float,
    effective_age_cycles: float,
    operational_load: float,
    contamination: float,
    humidity: float,
    temperature_stress: float,
    maintenance_level: float,
    linear_guide_health: float,
    torque_margin: float,
    current_draw_factor: float,
    vibration_index: float,
    previous_damage_per_usage: float,
) -> list[float]:
    return [
        float(previous_health),
        float(effective_age_cycles),
        float(operational_load),
        float(contamination),
        float(humidity),
        float(temperature_stress),
        float(maintenance_level),
        float(linear_guide_health),
        float(torque_margin),
        float(current_draw_factor),
        float(vibration_index),
        float(previous_damage_per_usage),
    ]


def _build_training_dataset(config: dict) -> tuple[list[list[float]], list[float]]:
    health_values = (0.16, 0.25, 0.4, 0.58, 0.75, 0.9, 1.0)
    load_values = (0.2, 0.72, 1.2, 2.0)
    contamination_values = (0.0, 0.35, 0.7, 1.0)
    humidity_values = (0.0, 0.5, 1.0)
    temperature_values = (0.0, 0.35, 0.7, 1.0)
    maintenance_values = (0.0, 0.55, 1.0)
    guide_health_values = (0.35, 0.7, 1.0)
    rows = []
    targets = []
    for health in health_values:
        for guide_health in guide_health_values:
            metrics = _metrics_from_health(config, health, guide_health)
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
                                    next_state = calculate_recoater_drive_motor_state(
                                        previous_state={"health": health},
                                        drivers=drivers,
                                        config=config,
                                        linear_guide_state={"health": guide_health},
                                    )
                                    mathematical_damage = float(next_state["damage"]["total"])
                                    previous_damage_per_usage = mathematical_damage * (
                                        0.35
                                        + 0.45 * (1.0 - health)
                                        + 0.2 * (1.0 - guide_health)
                                    )
                                    target_damage, _ = apply_hybrid_teacher(
                                        COMPONENT_ID,
                                        mathematical_damage,
                                        {
                                            "previous_health": health,
                                            "operational_load": operational_load,
                                            "contamination": contamination,
                                            "humidity": humidity,
                                            "temperature_stress": temperature_stress,
                                            "maintenance_level": maintenance_level,
                                            "linear_guide_health": guide_health,
                                            "previous_damage_per_usage": (
                                                previous_damage_per_usage
                                            ),
                                        },
                                    )
                                    rows.append(
                                        _feature_row(
                                            previous_health=health,
                                            effective_age_cycles=float(
                                                metrics["effective_age_cycles"]
                                            ),
                                            operational_load=operational_load,
                                            contamination=contamination,
                                            humidity=humidity,
                                            temperature_stress=temperature_stress,
                                            maintenance_level=maintenance_level,
                                            linear_guide_health=guide_health,
                                            torque_margin=float(metrics["torque_margin"]),
                                            current_draw_factor=float(
                                                metrics["current_draw_factor"]
                                            ),
                                            vibration_index=float(metrics["vibration_index"]),
                                            previous_damage_per_usage=(
                                                previous_damage_per_usage
                                            ),
                                        )
                                    )
                                    targets.append(target_damage * SYNTHETIC_LABEL_SCALE)

    return rows, targets


def train_recoater_drive_motor_model() -> tuple[HistGradientBoostingRegressor, dict]:
    started_at = perf_counter()
    config, uncertainty = with_ai_uncertainty(
        load_phase1_config(),
        COMPONENT_ID,
        MODEL_RANDOM_STATE,
    )
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
        "training_target": "damage_per_step",
        "ai_uncertainty": {
            "enabled": bool(uncertainty),
            **uncertainty,
        },
        "training_teacher": {
            "type": HEURISTIC_TEACHER_TYPE,
            "version": HEURISTIC_TEACHER_VERSION,
            "component_profile": COMPONENT_ID,
        },
        "trained_from_scratch": True,
    }


def _build_ai_curve(
    timeline: list[dict],
    model: HistGradientBoostingRegressor,
    config: dict,
) -> list[dict]:
    first_point = timeline[0]
    first_component = first_point["components"][COMPONENT_ID]
    first_metrics = first_component.get("metrics", {})
    ai_health = _component_health(first_component)
    previous_usage = float(first_point["usage_count"])
    previous_damage_per_usage = _clamp(
        (
            (1.0 - ai_health) * 0.006
            + max(float(first_metrics.get("vibration_index", 1.0)) - 1.0, 0.0) * 0.004
        ),
        0.0,
        1.0,
    )
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
        guide_health = _guide_health_from_point(point)
        metrics = _metrics_from_health(config, ai_health, guide_health)
        features = _feature_row(
            previous_health=ai_health,
            effective_age_cycles=float(metrics["effective_age_cycles"]),
            operational_load=float(drivers["operational_load"]),
            contamination=float(drivers["contamination"]),
            humidity=float(drivers["humidity"]),
            temperature_stress=float(drivers["temperature_stress"]),
            maintenance_level=float(drivers["maintenance_level"]),
            linear_guide_health=guide_health,
            torque_margin=float(metrics["torque_margin"]),
            current_draw_factor=float(metrics["current_draw_factor"]),
            vibration_index=float(metrics["vibration_index"]),
            previous_damage_per_usage=previous_damage_per_usage,
        )
        damage_per_step = max(float(model.predict([features])[0]), 0.0)
        damage = damage_per_step
        predicted_health = _clamp(ai_health - damage, 0.0, 1.0)
        ai_health = calibrate_ai_health(
            predicted_health=predicted_health,
            previous_health=ai_health,
        )
        previous_damage_per_usage = damage_per_step / max(usage_delta, 1.0)
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


def predict_recoater_drive_motor_ai_from_timeline(run_id: str, timeline: list[dict]) -> dict:
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
            "model_family": "recoater_drive_motor_sklearn_gradient_boosting",
            "prediction_method": "supervised_synthetic_gradient_boosting",
            "reason": "Not enough motor history for the AI predictor.",
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
        "model_family": "recoater_drive_motor_sklearn_gradient_boosting",
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
            "target": "damage_per_step",
            "feature_names": list(FEATURE_NAMES),
            "top_factors": [
                {"name": "effective_age_cycles", "direction": "state"},
                {"name": "linear_guide_health", "direction": "risk"},
                {"name": "temperature_stress", "direction": "risk"},
                {"name": "contamination", "direction": "risk"},
                {"name": "maintenance_level", "direction": "protective"},
                {"name": "maintenance_error_index", "direction": "risk"},
                {"name": "failure_risk_index", "direction": "risk"},
            ],
        },
    }
