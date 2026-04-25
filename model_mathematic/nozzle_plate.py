"""Nozzle Plate degradation model.

The Nozzle Plate model represents degradation caused by clogging and thermal
fatigue. Clogging is amplified by contamination, humidity, and degradation of
the Recoater Blade. Thermal fatigue is amplified by temperature stress and can
also be affected by degraded Heating Elements.

This model is deterministic and belongs to Phase 1. It does not know about
timestamps, scenario IDs, run IDs, persistence, or simulation steps.
"""

from .common import DAMAGE_PRECISION, HEALTH_PRECISION, clamp, get_status_from_health


COMPONENT_NAME = "nozzle_plate"


def _get_component_config(config):
    if "components" in config:
        return config["components"][COMPONENT_NAME]
    return config


def _get_previous_component_state(previous_state):
    if not previous_state:
        return {}

    if "components" in previous_state:
        return previous_state.get("components", {}).get(COMPONENT_NAME, {})

    return previous_state


def _get_previous_health(previous_state, health_config):
    component_state = _get_previous_component_state(previous_state)
    return component_state.get("health", health_config["initial"])


def _get_previous_metric(previous_state, metric_name, default_value=0.0):
    component_state = _get_previous_component_state(previous_state)
    metrics = component_state.get("metrics", {})
    return metrics.get(metric_name, default_value)


def _get_component_health(component_state):
    if not component_state:
        return 1.0

    return clamp(
        float(component_state.get("health", 1.0)),
        0.0,
        1.0,
    )


def _build_alerts(
    status,
    clogging_ratio,
    thermal_fatigue_index,
    jetting_efficiency,
    alerts_config,
):
    alerts = []

    if clogging_ratio >= alerts_config["high_clogging_threshold"]:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "HIGH_CLOGGING",
                "message": "Nozzle plate clogging ratio exceeds configured threshold.",
            }
        )

    if thermal_fatigue_index >= alerts_config["high_thermal_fatigue_threshold"]:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "HIGH_THERMAL_FATIGUE",
                "message": "Nozzle plate thermal fatigue exceeds configured threshold.",
            }
        )

    if jetting_efficiency <= alerts_config["low_jetting_efficiency_threshold"]:
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "LOW_JETTING_EFFICIENCY",
                "message": "Nozzle plate jetting efficiency is below configured threshold.",
            }
        )

    if status == "FAILED":
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "COMPONENT_FAILED",
                "message": "Nozzle plate health is below the failure threshold.",
            }
        )

    return alerts


def calculate_nozzle_plate_state(
    previous_state: dict,
    drivers: dict,
    config: dict,
    recoater_blade_state: dict | None = None,
    heating_elements_state: dict | None = None,
) -> dict:
    """Calculate the deterministic Phase 1 state for the nozzle plate."""
    component_config = _get_component_config(config)
    health_config = component_config["health"]
    calibration_config = component_config["calibration"]
    sensitivity = component_config["sensitivity"]
    damage_weights = component_config["damage_weights"]
    metrics_config = component_config["metrics"]
    alerts_config = component_config["alerts"]

    previous_health = clamp(
        float(_get_previous_health(previous_state, health_config)),
        health_config["min"],
        health_config["max"],
    )

    previous_clogging_ratio = clamp(
        float(_get_previous_metric(previous_state, "clogging_ratio", 0.0)),
        0.0,
        1.0,
    )

    previous_thermal_fatigue_index = clamp(
        float(_get_previous_metric(previous_state, "thermal_fatigue_index", 0.0)),
        0.0,
        1.0,
    )

    drivers = drivers or {}

    operational_load = max(float(drivers.get("operational_load", 0.0)), 0.0)
    contamination = clamp(float(drivers.get("contamination", 0.0)), 0.0, 1.0)
    humidity = clamp(float(drivers.get("humidity", 0.0)), 0.0, 1.0)
    temperature_stress = clamp(float(drivers.get("temperature_stress", 0.0)), 0.0, 1.0)
    maintenance_level = clamp(float(drivers.get("maintenance_level", 0.0)), 0.0, 1.0)

    recoater_blade_health = _get_component_health(recoater_blade_state)
    heating_elements_health = _get_component_health(heating_elements_state)

    base_damage_per_cycle = (
        health_config["initial"] - calibration_config["failure_threshold"]
    ) / calibration_config["target_cycles_until_failure"]

    load_factor = operational_load ** sensitivity["load_exponent"]

    recoater_degradation = 1.0 - recoater_blade_health
    heating_degradation = 1.0 - heating_elements_health

    effective_contamination = clamp(
        contamination + sensitivity["recoater_cascade"] * recoater_degradation,
        0.0,
        1.0,
    )

    effective_temperature_stress = clamp(
        temperature_stress
        + sensitivity.get("heating_cascade", 0.0) * heating_degradation,
        0.0,
        1.0,
    )

    contamination_factor = 1.0 + sensitivity["contamination"] * effective_contamination
    humidity_factor = 1.0 + sensitivity["humidity"] * humidity
    temperature_factor = (
        1.0 + sensitivity["temperature_stress"] * effective_temperature_stress
    )
    maintenance_factor = 1.0 - sensitivity["maintenance_protection"] * maintenance_level

    base_damage = base_damage_per_cycle * load_factor

    raw_clogging_damage = (
        base_damage
        * damage_weights["clogging"]
        * contamination_factor
        * humidity_factor
    )

    raw_thermal_fatigue_damage = (
        base_damage
        * damage_weights["thermal_fatigue"]
        * temperature_factor
    )

    raw_total_damage = (
        raw_clogging_damage + raw_thermal_fatigue_damage
    ) * maintenance_factor

    damage = clamp(
        raw_total_damage,
        0.0,
        previous_health - health_config["min"],
    )

    if raw_total_damage > 0:
        damage_scale = damage / raw_total_damage
    else:
        damage_scale = 0.0

    clogging_damage = raw_clogging_damage * maintenance_factor * damage_scale
    thermal_fatigue_damage = (
        raw_thermal_fatigue_damage * maintenance_factor * damage_scale
    )

    new_health = clamp(
        previous_health - damage,
        health_config["min"],
        health_config["max"],
    )

    rounded_health = round(new_health, HEALTH_PRECISION)
    reported_damage = max(
        0.0,
        round(previous_health - rounded_health, DAMAGE_PRECISION),
    )
    status = get_status_from_health(rounded_health, health_config)

    if damage > 0:
        reported_damage_scale = reported_damage / damage
    else:
        reported_damage_scale = 0.0

    reported_clogging_damage = clogging_damage * reported_damage_scale
    reported_thermal_fatigue_damage = thermal_fatigue_damage * reported_damage_scale

    clogging_ratio = clamp(
        previous_clogging_ratio + reported_clogging_damage,
        0.0,
        1.0,
    )

    thermal_fatigue_index = clamp(
        previous_thermal_fatigue_index + reported_thermal_fatigue_damage,
        0.0,
        1.0,
    )

    blocked_nozzles_pct = (
        metrics_config["max_blocked_nozzles_pct"] * clogging_ratio
    )

    jetting_efficiency = clamp(
        rounded_health * (1.0 - 0.5 * clogging_ratio),
        metrics_config["min_jetting_efficiency"],
        1.0,
    )

    rounded_clogging_ratio = round(clogging_ratio, 6)
    rounded_thermal_fatigue_index = round(thermal_fatigue_index, 6)
    rounded_jetting_efficiency = round(jetting_efficiency, 6)

    return {
        "subsystem": component_config["subsystem"],
        "component": COMPONENT_NAME,
        "health": rounded_health,
        "status": status,
        "damage": {
            "total": reported_damage,
            "clogging": round(reported_clogging_damage, DAMAGE_PRECISION),
            "thermal_fatigue": round(
                reported_thermal_fatigue_damage,
                DAMAGE_PRECISION,
            ),
        },
        "metrics": {
            "effective_contamination": round(effective_contamination, 6),
            "effective_temperature_stress": round(effective_temperature_stress, 6),
            "recoater_blade_health": round(recoater_blade_health, 6),
            "heating_elements_health": round(heating_elements_health, 6),
            "clogging_ratio": rounded_clogging_ratio,
            "blocked_nozzles_pct": round(blocked_nozzles_pct, 6),
            "thermal_fatigue_index": rounded_thermal_fatigue_index,
            "jetting_efficiency": rounded_jetting_efficiency,
            "contamination_factor": round(contamination_factor, 6),
            "humidity_factor": round(humidity_factor, 6),
            "temperature_factor": round(temperature_factor, 6),
            "maintenance_factor": round(maintenance_factor, 6),
        },
        "alerts": _build_alerts(
            status=status,
            clogging_ratio=rounded_clogging_ratio,
            thermal_fatigue_index=rounded_thermal_fatigue_index,
            jetting_efficiency=rounded_jetting_efficiency,
            alerts_config=alerts_config,
        ),
    }
