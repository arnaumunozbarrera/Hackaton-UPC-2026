"""Temperature Sensors degradation model for the thermal control subsystem."""

from .common import (
    HEALTH_PRECISION,
    clamp,
    get_component_config,
    get_previous_health,
    get_reported_damage,
    get_status_from_health,
    snap_health_to_failure_threshold,
    split_damage_by_pressure,
)


COMPONENT_NAME = "temperature_sensors"


def _build_alerts(status, drift_c, response_time_ms, calibration_confidence, alerts_config):
    alerts = []

    if abs(drift_c) >= alerts_config["high_drift_threshold_c"]:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "HIGH_SENSOR_DRIFT",
                "message": "Temperature sensor drift exceeds threshold.",
            }
        )

    if response_time_ms >= alerts_config["high_response_time_ms"]:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "SLOW_SENSOR_RESPONSE",
                "message": "Temperature sensor response time exceeds threshold.",
            }
        )

    if calibration_confidence <= alerts_config["low_calibration_confidence_threshold"]:
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "LOW_CALIBRATION_CONFIDENCE",
                "message": "Temperature sensor calibration confidence is below threshold.",
            }
        )

    if status == "FAILED":
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "COMPONENT_FAILED",
                "message": "Temperature sensors health is below the failure threshold.",
            }
        )

    return alerts


def calculate_temperature_sensors_state(
    previous_state: dict,
    drivers: dict,
    config: dict,
) -> dict:
    """Calculate deterministic drift, noise, and response degradation."""
    component_config = get_component_config(config, COMPONENT_NAME)
    health_config = component_config["health"]
    calibration_config = component_config["calibration"]
    sensitivity = component_config["sensitivity"]
    physical_properties = component_config["physical_properties"]
    alerts_config = component_config["alerts"]

    previous_health = clamp(
        float(get_previous_health(previous_state, COMPONENT_NAME, health_config)),
        health_config["min"],
        health_config["max"],
    )

    drivers = drivers or {}

    operational_load = max(float(drivers.get("operational_load", 0.0)), 0.0)
    temperature_stress = clamp(float(drivers.get("temperature_stress", 0.0)), 0.0, 1.0)
    humidity = clamp(float(drivers.get("humidity", 0.0)), 0.0, 1.0)
    maintenance_level = clamp(float(drivers.get("maintenance_level", 0.0)), 0.0, 1.0)

    base_damage_per_cycle = (
        health_config["initial"] - calibration_config["failure_threshold"]
    ) / calibration_config["target_cycles_until_failure"]

    temperature_factor = 1.0 + sensitivity["temperature_stress"] * temperature_stress
    humidity_factor = 1.0 + sensitivity["humidity"] * humidity
    maintenance_factor = 1.0 - sensitivity["maintenance_protection"] * maintenance_level

    raw_damage = (
        base_damage_per_cycle
        * operational_load ** sensitivity["load_exponent"]
        * temperature_factor
        * humidity_factor
        * maintenance_factor
    )

    damage = clamp(raw_damage, 0.0, previous_health - health_config["min"])
    new_health = clamp(
        previous_health - damage,
        health_config["min"],
        health_config["max"],
    )

    rounded_health = round(new_health, HEALTH_PRECISION)
    rounded_health = snap_health_to_failure_threshold(rounded_health, health_config)
    reported_damage = get_reported_damage(previous_health, rounded_health)
    status = get_status_from_health(rounded_health, health_config)

    degradation_ratio = 1.0 - rounded_health

    drift_c = (
        physical_properties["max_drift_c"]
        * degradation_ratio
        * (1.0 + temperature_stress)
    )
    response_time_ms = (
        physical_properties["nominal_response_time_ms"]
        + physical_properties["max_response_delay_ms"] * degradation_ratio
    )
    signal_noise_index = clamp(
        physical_properties["max_signal_noise_index"]
        * degradation_ratio
        * (1.0 + humidity),
        0.0,
        physical_properties["max_signal_noise_index"] * 2.0,
    )
    calibration_confidence = clamp(
        1.0 - physical_properties["max_calibration_confidence_loss"] * degradation_ratio,
        0.0,
        1.0,
    )

    pressures = {
        "signal_aging": 1.0,
        "thermal_drift": sensitivity["temperature_stress"] * temperature_stress,
        "humidity_corrosion": sensitivity["humidity"] * humidity,
    }
    damage_breakdown = {"total": reported_damage}
    damage_breakdown.update(split_damage_by_pressure(reported_damage, pressures))

    rounded_drift = round(drift_c, 6)
    rounded_response_time = round(response_time_ms, 6)
    rounded_confidence = round(calibration_confidence, 6)

    return {
        "subsystem": component_config["subsystem"],
        "component": COMPONENT_NAME,
        "health": rounded_health,
        "status": status,
        "damage": damage_breakdown,
        "metrics": {
            "drift_c": rounded_drift,
            "response_time_ms": rounded_response_time,
            "signal_noise_index": round(signal_noise_index, 6),
            "calibration_confidence": rounded_confidence,
            "temperature_factor": round(temperature_factor, 6),
            "humidity_factor": round(humidity_factor, 6),
            "maintenance_factor": round(maintenance_factor, 6),
        },
        "alerts": _build_alerts(
            status,
            rounded_drift,
            rounded_response_time,
            rounded_confidence,
            alerts_config,
        ),
    }
