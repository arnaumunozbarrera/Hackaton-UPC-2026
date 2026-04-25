"""Nozzle Plate degradation model.

The Nozzle Plate model represents degradation caused by clogging and thermal
fatigue. Clogging is amplified by contamination, humidity, and degradation of
the Recoater Blade. Thermal fatigue is amplified by temperature stress and can
also be affected by degraded Heating Elements.

This model is deterministic and belongs to Phase 1. It does not know about
timestamps, scenario IDs, run IDs, persistence, or simulation steps.
"""

from .common import (
    DAMAGE_PRECISION,
    HEALTH_PRECISION,
    clamp,
    deterministic_signed_noise,
    get_component_config,
    get_component_health,
    get_previous_component_state,
    get_previous_health,
    get_reported_damage,
    get_simulation_seed,
    get_status_from_health,
    snap_health_to_failure_threshold,
    split_damage_by_pressure,
)


COMPONENT_NAME = "nozzle_plate"


def _get_previous_metric(previous_state, metric_name, default_value=0.0):
    component_state = get_previous_component_state(previous_state, COMPONENT_NAME)
    metrics = component_state.get("metrics", {})
    return metrics.get(metric_name, default_value)


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
    cleaning_interface_state: dict | None = None,
    thermal_firing_resistors_state: dict | None = None,
) -> dict:
    """Calculate the deterministic Phase 1 state for the nozzle plate."""
    component_config = get_component_config(config, COMPONENT_NAME)
    health_config = component_config["health"]
    calibration_config = component_config["calibration"]
    sensitivity = component_config["sensitivity"]
    damage_weights = component_config["damage_weights"]
    metrics_config = component_config["metrics"]
    alerts_config = component_config["alerts"]
    uncertainty_config = component_config.get("uncertainty", {})

    previous_health = clamp(
        float(get_previous_health(previous_state, COMPONENT_NAME, health_config)),
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
    seed = get_simulation_seed(config)

    recoater_blade_health = get_component_health(recoater_blade_state)
    heating_elements_health = get_component_health(heating_elements_state)
    cleaning_interface_health = get_component_health(cleaning_interface_state)
    thermal_firing_resistors_health = get_component_health(
        thermal_firing_resistors_state
    )

    base_damage_per_cycle = (
        health_config["initial"] - calibration_config["failure_threshold"]
    ) / calibration_config["target_cycles_until_failure"]

    load_factor = operational_load ** sensitivity["load_exponent"]

    recoater_degradation = 1.0 - recoater_blade_health
    heating_degradation = 1.0 - heating_elements_health
    cleaning_degradation = 1.0 - cleaning_interface_health
    firing_resistor_degradation = 1.0 - thermal_firing_resistors_health

    effective_contamination = clamp(
        contamination
        + sensitivity["recoater_cascade"] * recoater_degradation
        + sensitivity.get("cleaning_cascade", 0.0) * cleaning_degradation,
        0.0,
        1.0,
    )

    effective_temperature_stress = clamp(
        temperature_stress
        + sensitivity.get("heating_cascade", 0.0) * heating_degradation
        + sensitivity.get("firing_resistor_cascade", 0.0)
        * firing_resistor_degradation,
        0.0,
        1.0,
    )

    contamination_factor = 1.0 + sensitivity["contamination"] * effective_contamination
    humidity_factor = 1.0 + sensitivity["humidity"] * humidity
    temperature_factor = (
        1.0 + sensitivity["temperature_stress"] * effective_temperature_stress
    )
    maintenance_factor = 1.0 - sensitivity["maintenance_protection"] * maintenance_level
    maintenance_error_rate = clamp(
        float(uncertainty_config.get("maintenance_error_rate", 0.0)),
        0.0,
        1.0,
    )
    failure_risk_scale = clamp(
        float(uncertainty_config.get("failure_risk_scale", 0.0)),
        0.0,
        1.0,
    )
    maintenance_noise = deterministic_signed_noise(
        seed,
        COMPONENT_NAME,
        "maintenance_error",
        round(previous_health, HEALTH_PRECISION),
        operational_load,
        contamination,
        humidity,
        temperature_stress,
        maintenance_level,
        round(previous_clogging_ratio, 6),
        round(previous_thermal_fatigue_index, 6),
    )
    maintenance_noise_factor = 0.5 * (maintenance_noise + 1.0)
    maintenance_error_index = (
        maintenance_error_rate
        * (1.0 - maintenance_level)
        * maintenance_noise_factor
    )
    failure_risk_index = (
        failure_risk_scale
        * (1.0 - maintenance_level)
        * maintenance_noise_factor
    )

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

    physical_total_damage = (
        raw_clogging_damage + raw_thermal_fatigue_damage
    ) * maintenance_factor
    uncertainty_damage = (
        base_damage
        * failure_risk_index
    )
    raw_total_damage = physical_total_damage + uncertainty_damage

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
    uncertainty_damage = uncertainty_damage * damage_scale

    new_health = clamp(
        previous_health - damage,
        health_config["min"],
        health_config["max"],
    )

    rounded_health = round(new_health, HEALTH_PRECISION)
    rounded_health = snap_health_to_failure_threshold(rounded_health, health_config)
    reported_damage = get_reported_damage(previous_health, rounded_health)
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

    clogging_penalty = metrics_config["jetting_efficiency_clogging_penalty"]

    jetting_efficiency = clamp(
        rounded_health * (1.0 - clogging_penalty * clogging_ratio),
        metrics_config["min_jetting_efficiency"],
        1.0,
    )

    rounded_clogging_ratio = round(clogging_ratio, 6)
    rounded_thermal_fatigue_index = round(thermal_fatigue_index, 6)
    rounded_jetting_efficiency = round(jetting_efficiency, 6)
    damage_breakdown = {"total": reported_damage}
    damage_breakdown.update(
        split_damage_by_pressure(
            reported_damage,
            {
                "clogging": max(clogging_damage, 0.0),
                "thermal_fatigue": max(thermal_fatigue_damage, 0.0),
                "maintenance_uncertainty": max(uncertainty_damage, 0.0),
            },
        )
    )

    return {
        "subsystem": component_config["subsystem"],
        "component": COMPONENT_NAME,
        "health": rounded_health,
        "status": status,
        "damage": damage_breakdown,
        "metrics": {
            "effective_contamination": round(effective_contamination, 6),
            "effective_temperature_stress": round(effective_temperature_stress, 6),
            "recoater_blade_health": round(recoater_blade_health, 6),
            "heating_elements_health": round(heating_elements_health, 6),
            "cleaning_interface_health": round(cleaning_interface_health, 6),
            "thermal_firing_resistors_health": round(
                thermal_firing_resistors_health,
                6,
            ),
            "clogging_ratio": rounded_clogging_ratio,
            "blocked_nozzles_pct": round(blocked_nozzles_pct, 6),
            "thermal_fatigue_index": rounded_thermal_fatigue_index,
            "jetting_efficiency": rounded_jetting_efficiency,
            "jetting_efficiency_clogging_penalty": round(clogging_penalty, 6),
            "contamination_factor": round(contamination_factor, 6),
            "humidity_factor": round(humidity_factor, 6),
            "temperature_factor": round(temperature_factor, 6),
            "maintenance_factor": round(maintenance_factor, 6),
            "maintenance_error_index": round(maintenance_error_index, 6),
            "failure_risk_index": round(failure_risk_index, 6),
            "uncertainty_damage": round(uncertainty_damage, 8),
            "seed": seed,
        },
        "alerts": _build_alerts(
            status=status,
            clogging_ratio=rounded_clogging_ratio,
            thermal_fatigue_index=rounded_thermal_fatigue_index,
            jetting_efficiency=rounded_jetting_efficiency,
            alerts_config=alerts_config,
        ),
    }
