"""Scikit-learn AI predictor for the recoater blade.

This module trains a HistGradientBoostingRegressor from scratch on deterministic
synthetic telemetry generated from the Phase 1 recoater blade model. The trained
model predicts damage per usage, then a parallel AI health curve is rolled
forward over the same usage points as the mathematical simulation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from time import perf_counter

from app.core.phase1 import load_phase1_config
from app.prediction.ai_curve_utils import calibrate_ai_health
from model_mathematic.recoater_blade import calculate_recoater_blade_state
from sklearn.ensemble import HistGradientBoostingRegressor


COMPONENT_ID = "recoater_blade"
PREVENTIVE_FAILURE_THRESHOLD = 0.15
MODEL_RANDOM_STATE = 2026
SYNTHETIC_LABEL_SCALE = 1.0

FEATURE_NAMES = (
    "previous_health",
    "operational_load",
    "contamination",
    "humidity",
    "maintenance_level",
    "thickness_mm",
    "roughness_index",
    "previous_wear_rate",
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


def _metrics_from_health(config: dict, health: float) -> dict:
    state = calculate_recoater_blade_state(
        previous_state={"health": health},
        drivers={
            "operational_load": 0.0,
            "contamination": 0.0,
            "humidity": 0.0,
            "temperature_stress": 0.0,
            "maintenance_level": 0.0,
        },
        config=config,
    )
    return state["metrics"]


def _feature_row(
    previous_health: float,
    operational_load: float,
    contamination: float,
    humidity: float,
    maintenance_level: float,
    thickness_mm: float,
    roughness_index: float,
    previous_wear_rate: float,
    usage_count: float,
) -> list[float]:
    return [
        float(previous_health),
        float(operational_load),
        float(contamination),
        float(humidity),
        float(maintenance_level),
        float(thickness_mm),
        float(roughness_index),
        float(previous_wear_rate),
        float(usage_count),
    ]


def _synthetic_label_multiplier(
    usage_count: float,
    contamination: float,
    humidity: float,
    maintenance_level: float,
    previous_health: float,
) -> float:
    """Deterministic telemetry residual used to avoid a perfect formula clone."""
    degradation = 1.0 - previous_health
    interaction = contamination * humidity * (1.0 - maintenance_level)
    periodic_residual = (
        ((usage_count * 0.017 + contamination * 1.9 + humidity * 1.3) % 1.0) - 0.5
    )
    multiplier = (
        1.0
        + 0.08 * interaction
        + 0.04 * degradation**2
        + 0.035 * periodic_residual
    )
    return _clamp(multiplier, 0.92, 1.16)


def _build_training_dataset(config: dict) -> tuple[list[list[float]], list[float]]:
    health_values = (0.16, 0.22, 0.3, 0.4, 0.55, 0.7, 0.85, 1.0)
    load_values = (0.15, 0.35, 0.72, 1.0, 1.4, 2.0)
    contamination_values = (0.0, 0.2, 0.4, 0.6, 0.85, 1.0)
    humidity_values = (0.0, 0.25, 0.5, 0.75, 1.0)
    maintenance_values = (0.0, 0.25, 0.5, 0.75, 1.0)
    usage_values = (0.0, 250.0, 750.0, 1500.0, 2250.0, 3000.0)

    rows = []
    targets = []
    for health in health_values:
        metrics = _metrics_from_health(config, health)
        for operational_load in load_values:
            for contamination in contamination_values:
                for humidity in humidity_values:
                    for maintenance_level in maintenance_values:
                        for usage_count in usage_values:
                            drivers = {
                                "operational_load": operational_load,
                                "contamination": contamination,
                                "humidity": humidity,
                                "temperature_stress": 0.0,
                                "maintenance_level": maintenance_level,
                            }
                            next_state = calculate_recoater_blade_state(
                                previous_state={"health": health},
                                drivers=drivers,
                                config=config,
                            )
                            mathematical_damage = float(next_state["damage"]["total"])
                            multiplier = _synthetic_label_multiplier(
                                usage_count,
                                contamination,
                                humidity,
                                maintenance_level,
                                health,
                            )
                            rows.append(
                                _feature_row(
                                    previous_health=health,
                                    operational_load=operational_load,
                                    contamination=contamination,
                                    humidity=humidity,
                                    maintenance_level=maintenance_level,
                                    thickness_mm=float(metrics["thickness_mm"]),
                                    roughness_index=float(metrics["roughness_index"]),
                                    previous_wear_rate=0.0,
                                    usage_count=usage_count,
                                )
                            )
                            targets.append(
                                mathematical_damage * multiplier * SYNTHETIC_LABEL_SCALE
                            )

    return rows, targets


def train_recoater_blade_model() -> tuple[HistGradientBoostingRegressor, dict]:
    started_at = perf_counter()
    config = load_phase1_config()
    rows, targets = _build_training_dataset(config)
    model = HistGradientBoostingRegressor(
        max_iter=140,
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
    previous_wear_rate = 0.0
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
        metrics = _metrics_from_health(config, ai_health)
        features = _feature_row(
            previous_health=ai_health,
            operational_load=float(drivers["operational_load"]),
            contamination=float(drivers["contamination"]),
            humidity=float(drivers["humidity"]),
            maintenance_level=float(drivers["maintenance_level"]),
            thickness_mm=float(metrics["thickness_mm"]),
            roughness_index=float(metrics["roughness_index"]),
            previous_wear_rate=previous_wear_rate,
            usage_count=usage_count,
        )
        damage_per_usage = max(float(model.predict([features])[0]), 0.0)
        damage = damage_per_usage * usage_delta
        predicted_health = _clamp(ai_health - damage, 0.0, 1.0)
        ai_health = calibrate_ai_health(
            predicted_health=predicted_health,
            mathematical_health=_component_health(point["components"][COMPONENT_ID]),
            previous_health=ai_health,
            usage_count=usage_count,
            drivers=drivers,
            component_phase=0.2,
        )
        previous_wear_rate = damage_per_usage
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


def predict_recoater_blade_ai_from_timeline(run_id: str, timeline: list[dict]) -> dict:
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
            "model_family": "recoater_blade_sklearn_gradient_boosting",
            "prediction_method": "supervised_synthetic_gradient_boosting",
            "reason": "Not enough recoater blade history for the AI predictor.",
        }

    config = load_phase1_config()
    model, training = train_recoater_blade_model()
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

    confidence = 0.64 + min(len(points) / 750.0, 0.18)
    if failure_point is not None:
        confidence += 0.07

    return {
        "run_id": run_id,
        "component_id": COMPONENT_ID,
        "predicted_failure_timestamp": predicted_failure_timestamp,
        "predicted_failure_usage": predicted_failure_usage,
        "confidence": round(_clamp(confidence, 0.2, 0.91), 2),
        "model_family": "recoater_blade_sklearn_gradient_boosting",
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
                {"name": "contamination", "direction": "risk"},
                {"name": "humidity", "direction": "risk"},
                {"name": "maintenance_level", "direction": "protective"},
                {"name": "previous_health", "direction": "state"},
            ],
        },
    }


def predict_recoater_blade_failure_from_timeline(run_id: str, timeline: list[dict]) -> dict:
    """Backward-compatible alias for callers that still use the old name."""
    return predict_recoater_blade_ai_from_timeline(run_id, timeline)
