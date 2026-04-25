"""Scikit-learn AI predictor for the nozzle plate."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from time import perf_counter

from app.core.phase1 import load_phase1_config
from app.prediction.ai_curve_utils import calibrate_ai_health
from model_mathematic.nozzle_plate import calculate_nozzle_plate_state
from sklearn.ensemble import HistGradientBoostingRegressor


COMPONENT_ID = "nozzle_plate"
PREVENTIVE_FAILURE_THRESHOLD = 0.15
MODEL_RANDOM_STATE = 2026
SYNTHETIC_LABEL_SCALE = 1.0

FEATURE_NAMES = (
    "previous_health",
    "previous_clogging_ratio",
    "previous_thermal_fatigue_index",
    "operational_load",
    "contamination",
    "humidity",
    "temperature_stress",
    "maintenance_level",
    "recoater_blade_health",
    "heating_elements_health",
    "cleaning_interface_health",
    "thermal_firing_resistors_health",
    "effective_contamination",
    "effective_temperature_stress",
    "blocked_nozzles_pct",
    "jetting_efficiency",
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


def _dependency_states(
    recoater_blade_health: float,
    heating_elements_health: float,
    cleaning_interface_health: float,
    thermal_firing_resistors_health: float,
) -> dict:
    return {
        "recoater_blade_state": {"health": recoater_blade_health},
        "heating_elements_state": {"health": heating_elements_health},
        "cleaning_interface_state": {"health": cleaning_interface_health},
        "thermal_firing_resistors_state": {"health": thermal_firing_resistors_health},
    }


def _dependency_healths_from_point(point: dict) -> dict:
    components = point.get("components", {})
    nozzle_metrics = components.get(COMPONENT_ID, {}).get("metrics", {})

    def health_for(component_id: str, metric_name: str) -> float:
        dependency_state = components.get(component_id)
        if dependency_state is not None:
            return _component_health(dependency_state)
        return float(nozzle_metrics.get(metric_name, 1.0))

    return {
        "recoater_blade_health": health_for(
            "recoater_blade",
            "recoater_blade_health",
        ),
        "heating_elements_health": health_for(
            "heating_elements",
            "heating_elements_health",
        ),
        "cleaning_interface_health": health_for(
            "cleaning_interface",
            "cleaning_interface_health",
        ),
        "thermal_firing_resistors_health": health_for(
            "thermal_firing_resistors",
            "thermal_firing_resistors_health",
        ),
    }


def _previous_state(
    health: float,
    clogging_ratio: float,
    thermal_fatigue_index: float,
) -> dict:
    return {
        "health": health,
        "metrics": {
            "clogging_ratio": clogging_ratio,
            "thermal_fatigue_index": thermal_fatigue_index,
        },
    }


def _metrics_from_state(
    config: dict,
    health: float,
    clogging_ratio: float,
    thermal_fatigue_index: float,
    drivers: dict,
    dependency_healths: dict,
) -> dict:
    no_load_drivers = dict(drivers)
    no_load_drivers["operational_load"] = 0.0
    state = calculate_nozzle_plate_state(
        previous_state=_previous_state(
            health,
            clogging_ratio,
            thermal_fatigue_index,
        ),
        drivers=no_load_drivers,
        config=config,
        **_dependency_states(**dependency_healths),
    )
    return state["metrics"]


def _next_state(
    config: dict,
    health: float,
    clogging_ratio: float,
    thermal_fatigue_index: float,
    drivers: dict,
    dependency_healths: dict,
) -> dict:
    return calculate_nozzle_plate_state(
        previous_state=_previous_state(
            health,
            clogging_ratio,
            thermal_fatigue_index,
        ),
        drivers=drivers,
        config=config,
        **_dependency_states(**dependency_healths),
    )


def _feature_row(
    previous_health: float,
    previous_clogging_ratio: float,
    previous_thermal_fatigue_index: float,
    operational_load: float,
    contamination: float,
    humidity: float,
    temperature_stress: float,
    maintenance_level: float,
    recoater_blade_health: float,
    heating_elements_health: float,
    cleaning_interface_health: float,
    thermal_firing_resistors_health: float,
    effective_contamination: float,
    effective_temperature_stress: float,
    blocked_nozzles_pct: float,
    jetting_efficiency: float,
    previous_damage_per_usage: float,
    usage_count: float,
) -> list[float]:
    return [
        float(previous_health),
        float(previous_clogging_ratio),
        float(previous_thermal_fatigue_index),
        float(operational_load),
        float(contamination),
        float(humidity),
        float(temperature_stress),
        float(maintenance_level),
        float(recoater_blade_health),
        float(heating_elements_health),
        float(cleaning_interface_health),
        float(thermal_firing_resistors_health),
        float(effective_contamination),
        float(effective_temperature_stress),
        float(blocked_nozzles_pct),
        float(jetting_efficiency),
        float(previous_damage_per_usage),
        float(usage_count),
    ]


def _synthetic_label_multiplier(
    usage_count: float,
    contamination: float,
    humidity: float,
    temperature_stress: float,
    maintenance_level: float,
    dependency_healths: dict,
    previous_clogging_ratio: float,
    previous_thermal_fatigue_index: float,
    previous_health: float,
) -> float:
    recoater_degradation = 1.0 - dependency_healths["recoater_blade_health"]
    cleaning_degradation = 1.0 - dependency_healths["cleaning_interface_health"]
    heating_degradation = 1.0 - dependency_healths["heating_elements_health"]
    firing_degradation = 1.0 - dependency_healths[
        "thermal_firing_resistors_health"
    ]
    clogging_memory = previous_clogging_ratio * (0.5 + 0.5 * contamination)
    thermal_memory = previous_thermal_fatigue_index * (
        0.5 + 0.5 * temperature_stress
    )
    degradation = 1.0 - previous_health
    periodic_residual = (
        (
            usage_count * 0.009
            + contamination * 1.5
            + humidity * 1.1
            + temperature_stress * 1.7
            + cleaning_degradation * 1.9
        )
        % 1.0
    ) - 0.5
    multiplier = (
        1.0
        + 0.08 * clogging_memory
        + 0.07 * thermal_memory
        + 0.06 * (recoater_degradation + cleaning_degradation)
        + 0.05 * (heating_degradation + firing_degradation)
        + 0.04 * degradation**2
        - 0.05 * maintenance_level
        + 0.035 * periodic_residual
    )
    return _clamp(multiplier, 0.9, 1.24)


def _build_training_dataset(config: dict) -> tuple[list[list[float]], list[float]]:
    health_values = (0.16, 0.28, 0.45, 0.62, 0.8, 1.0)
    accumulated_damage_values = (
        (0.0, 0.0),
        (0.12, 0.04),
        (0.32, 0.12),
        (0.52, 0.28),
    )
    load_values = (0.2, 0.72, 1.2, 1.8)
    contamination_values = (0.0, 0.35, 0.7, 1.0)
    humidity_values = (0.0, 0.5, 1.0)
    temperature_values = (0.0, 0.5, 1.0)
    maintenance_values = (0.0, 0.55, 1.0)
    dependency_scenarios = (
        {
            "recoater_blade_health": 1.0,
            "heating_elements_health": 1.0,
            "cleaning_interface_health": 1.0,
            "thermal_firing_resistors_health": 1.0,
        },
        {
            "recoater_blade_health": 0.45,
            "heating_elements_health": 1.0,
            "cleaning_interface_health": 1.0,
            "thermal_firing_resistors_health": 1.0,
        },
        {
            "recoater_blade_health": 1.0,
            "heating_elements_health": 1.0,
            "cleaning_interface_health": 0.45,
            "thermal_firing_resistors_health": 1.0,
        },
        {
            "recoater_blade_health": 1.0,
            "heating_elements_health": 0.45,
            "cleaning_interface_health": 1.0,
            "thermal_firing_resistors_health": 0.45,
        },
        {
            "recoater_blade_health": 0.55,
            "heating_elements_health": 0.55,
            "cleaning_interface_health": 0.55,
            "thermal_firing_resistors_health": 0.55,
        },
    )
    usage_values = (0.0, 1800.0)

    rows = []
    targets = []
    for health in health_values:
        for clogging_ratio, thermal_fatigue_index in accumulated_damage_values:
            bounded_clogging = min(clogging_ratio, 1.0 - health + 0.1)
            bounded_thermal = min(thermal_fatigue_index, 1.0 - health + 0.1)
            for dependency_healths in dependency_scenarios:
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
                                    metrics = _metrics_from_state(
                                        config,
                                        health,
                                        bounded_clogging,
                                        bounded_thermal,
                                        drivers,
                                        dependency_healths,
                                    )
                                    next_state = _next_state(
                                        config,
                                        health,
                                        bounded_clogging,
                                        bounded_thermal,
                                        drivers,
                                        dependency_healths,
                                    )
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
                                            dependency_healths,
                                            bounded_clogging,
                                            bounded_thermal,
                                            health,
                                        )
                                        rows.append(
                                            _feature_row(
                                                previous_health=health,
                                                previous_clogging_ratio=bounded_clogging,
                                                previous_thermal_fatigue_index=bounded_thermal,
                                                operational_load=operational_load,
                                                contamination=contamination,
                                                humidity=humidity,
                                                temperature_stress=temperature_stress,
                                                maintenance_level=maintenance_level,
                                                effective_contamination=float(
                                                    metrics[
                                                        "effective_contamination"
                                                    ]
                                                ),
                                                effective_temperature_stress=float(
                                                    metrics[
                                                        "effective_temperature_stress"
                                                    ]
                                                ),
                                                blocked_nozzles_pct=float(
                                                    metrics["blocked_nozzles_pct"]
                                                ),
                                                jetting_efficiency=float(
                                                    metrics["jetting_efficiency"]
                                                ),
                                                previous_damage_per_usage=0.0,
                                                usage_count=usage_count,
                                                **dependency_healths,
                                            )
                                        )
                                        targets.append(
                                            mathematical_damage
                                            * multiplier
                                            * SYNTHETIC_LABEL_SCALE
                                        )

    return rows, targets


def train_nozzle_plate_model() -> tuple[HistGradientBoostingRegressor, dict]:
    started_at = perf_counter()
    config = load_phase1_config()
    rows, targets = _build_training_dataset(config)
    model = HistGradientBoostingRegressor(
        max_iter=135,
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
    first_metrics = first_component.get("metrics", {})
    ai_health = _component_health(first_component)
    ai_clogging_ratio = _clamp(first_metrics.get("clogging_ratio", 0.0), 0.0, 1.0)
    ai_thermal_fatigue_index = _clamp(
        first_metrics.get("thermal_fatigue_index", 0.0),
        0.0,
        1.0,
    )
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
        dependency_healths = _dependency_healths_from_point(point)
        metrics = _metrics_from_state(
            config,
            ai_health,
            ai_clogging_ratio,
            ai_thermal_fatigue_index,
            drivers,
            dependency_healths,
        )
        features = _feature_row(
            previous_health=ai_health,
            previous_clogging_ratio=ai_clogging_ratio,
            previous_thermal_fatigue_index=ai_thermal_fatigue_index,
            operational_load=float(drivers["operational_load"]),
            contamination=float(drivers["contamination"]),
            humidity=float(drivers["humidity"]),
            temperature_stress=float(drivers["temperature_stress"]),
            maintenance_level=float(drivers["maintenance_level"]),
            effective_contamination=float(metrics["effective_contamination"]),
            effective_temperature_stress=float(
                metrics["effective_temperature_stress"]
            ),
            blocked_nozzles_pct=float(metrics["blocked_nozzles_pct"]),
            jetting_efficiency=float(metrics["jetting_efficiency"]),
            previous_damage_per_usage=previous_damage_per_usage,
            usage_count=usage_count,
            **dependency_healths,
        )
        damage_per_usage = max(float(model.predict([features])[0]), 0.0)
        predicted_damage = damage_per_usage * usage_delta
        next_math_state = _next_state(
            config,
            ai_health,
            ai_clogging_ratio,
            ai_thermal_fatigue_index,
            drivers,
            dependency_healths,
        )
        mathematical_damage = float(next_math_state["damage"]["total"])
        if mathematical_damage > 0:
            clogging_share = (
                float(next_math_state["damage"]["clogging"]) / mathematical_damage
            )
        else:
            clogging_share = 0.65

        predicted_health = _clamp(ai_health - predicted_damage, 0.0, 1.0)
        new_ai_health = calibrate_ai_health(
            predicted_health=predicted_health,
            mathematical_health=_component_health(point["components"][COMPONENT_ID]),
            previous_health=ai_health,
            usage_count=usage_count,
            drivers=drivers,
            component_phase=2.0,
        )
        applied_damage = max(ai_health - new_ai_health, 0.0)
        ai_clogging_ratio = _clamp(
            ai_clogging_ratio + applied_damage * clogging_share,
            0.0,
            1.0,
        )
        ai_thermal_fatigue_index = _clamp(
            ai_thermal_fatigue_index + applied_damage * (1.0 - clogging_share),
            0.0,
            1.0,
        )
        ai_health = new_ai_health
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


def predict_nozzle_plate_ai_from_timeline(run_id: str, timeline: list[dict]) -> dict:
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
            "model_family": "nozzle_plate_sklearn_gradient_boosting",
            "prediction_method": "supervised_synthetic_gradient_boosting",
            "reason": "Not enough nozzle plate history for the AI predictor.",
        }

    config = load_phase1_config()
    model, training = train_nozzle_plate_model()
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

    confidence = 0.61 + min(len(points) / 750.0, 0.17)
    if failure_point is not None:
        confidence += 0.07

    return {
        "run_id": run_id,
        "component_id": COMPONENT_ID,
        "predicted_failure_timestamp": predicted_failure_timestamp,
        "predicted_failure_usage": predicted_failure_usage,
        "confidence": round(_clamp(confidence, 0.2, 0.9), 2),
        "model_family": "nozzle_plate_sklearn_gradient_boosting",
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
                {"name": "effective_contamination", "direction": "risk"},
                {"name": "effective_temperature_stress", "direction": "risk"},
                {"name": "clogging_ratio", "direction": "state"},
                {"name": "jetting_efficiency", "direction": "state"},
                {"name": "maintenance_level", "direction": "protective"},
            ],
        },
    }
