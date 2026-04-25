"""Recoater Drive Motor degradation model for the recoating system.

The motor uses a Weibull wear-out curve because mechanical fatigue and bearing
wear normally have increasing hazard with accumulated age. Environmental and
mechanical stressors increase effective age; the Weibull curve maps that age to
remaining health.
"""

import math

from .common import (
    HEALTH_PRECISION,
    clamp,
    get_component_config,
    get_component_health,
    get_previous_component_state,
    get_previous_health,
    get_reported_damage,
    get_status_from_health,
    snap_health_to_failure_threshold,
    split_damage_by_pressure,
)


COMPONENT_NAME = "recoater_drive_motor"


def _get_previous_metric(previous_state, metric_name, default_value=0.0):
    component_state = get_previous_component_state(previous_state, COMPONENT_NAME)
    metrics = component_state.get("metrics", {})
    return metrics.get(metric_name, default_value)


def _infer_weibull_age_from_health(
    health,
    initial_health,
    weibull_scale_cycles,
    weibull_shape_beta,
):
    if health >= initial_health:
        return 0.0

    reliability_ratio = clamp(health / initial_health, 1e-12, 1.0)
    cumulative_hazard = -math.log(reliability_ratio)
    return weibull_scale_cycles * cumulative_hazard ** (1.0 / weibull_shape_beta)


def _build_alerts(
    status,
    torque_margin,
    current_draw_factor,
    vibration_index,
    alerts_config,
):
    alerts = []

    if torque_margin <= alerts_config["low_torque_margin_threshold"]:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "LOW_TORQUE_MARGIN",
                "message": "Recoater drive motor torque margin is below threshold.",
            }
        )

    if current_draw_factor >= alerts_config["high_current_draw_factor"]:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "HIGH_CURRENT_DRAW",
                "message": "Recoater drive motor current draw exceeds threshold.",
            }
        )

    if vibration_index >= alerts_config["high_vibration_threshold"]:
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "HIGH_MOTOR_VIBRATION",
                "message": "Recoater drive motor vibration exceeds threshold.",
            }
        )

    if status == "FAILED":
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "COMPONENT_FAILED",
                "message": "Recoater drive motor health is below the failure threshold.",
            }
        )

    return alerts


def calculate_recoater_drive_motor_state(
    previous_state: dict,
    drivers: dict,
    config: dict,
    linear_guide_state: dict | None = None,
) -> dict:
    """Calculate deterministic Weibull fatigue, thermal stress, and ingress."""
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
    contamination = clamp(float(drivers.get("contamination", 0.0)), 0.0, 1.0)
    humidity = clamp(float(drivers.get("humidity", 0.0)), 0.0, 1.0)
    temperature_stress = clamp(float(drivers.get("temperature_stress", 0.0)), 0.0, 1.0)
    maintenance_level = clamp(float(drivers.get("maintenance_level", 0.0)), 0.0, 1.0)

    linear_guide_health = get_component_health(linear_guide_state)
    guide_degradation = 1.0 - linear_guide_health

    initial_health = health_config["initial"]
    failure_threshold = calibration_config["failure_threshold"]
    target_cycles_until_failure = calibration_config["target_cycles_until_failure"]
    weibull_shape_beta = float(calibration_config["weibull_shape_beta"])
    target_cumulative_hazard = -math.log(failure_threshold / initial_health)
    weibull_scale_cycles = target_cycles_until_failure / (
        target_cumulative_hazard ** (1.0 / weibull_shape_beta)
    )

    previous_effective_age_cycles = _get_previous_metric(
        previous_state,
        "effective_age_cycles",
        None,
    )
    if previous_effective_age_cycles is None:
        previous_effective_age_cycles = _infer_weibull_age_from_health(
            previous_health,
            initial_health,
            weibull_scale_cycles,
            weibull_shape_beta,
        )
    else:
        previous_effective_age_cycles = max(
            float(previous_effective_age_cycles),
            0.0,
        )

    guide_drag_factor = 1.0 + sensitivity["linear_guide_drag"] * guide_degradation
    contamination_factor = 1.0 + sensitivity["contamination"] * contamination
    humidity_factor = 1.0 + sensitivity["humidity"] * humidity
    temperature_factor = 1.0 + sensitivity["temperature_stress"] * temperature_stress
    maintenance_factor = 1.0 - sensitivity["maintenance_protection"] * maintenance_level

    effective_load = operational_load ** sensitivity["load_exponent"]
    effective_age_delta = (
        effective_load
        * guide_drag_factor
        * contamination_factor
        * humidity_factor
        * temperature_factor
        * maintenance_factor
    )
    effective_age_cycles = previous_effective_age_cycles + effective_age_delta

    cumulative_hazard = (effective_age_cycles / weibull_scale_cycles) ** (
        weibull_shape_beta
    )
    health_from_weibull = initial_health * math.exp(-cumulative_hazard)
    raw_damage = previous_health - min(previous_health, health_from_weibull)

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

    torque_margin = clamp(
        1.0
        - physical_properties["max_torque_margin_loss"] * degradation_ratio
        - physical_properties["guide_drag_torque_penalty"] * guide_degradation,
        0.0,
        1.0,
    )
    current_draw_factor = (
        1.0
        + physical_properties["max_current_draw_increase"] * degradation_ratio
        + physical_properties["guide_drag_current_penalty"] * guide_degradation
    )
    vibration_index = clamp(
        physical_properties["max_vibration_index"]
        * (degradation_ratio + 0.5 * guide_degradation),
        0.0,
        physical_properties["max_vibration_index"],
    )
    winding_temperature_rise_c = (
        physical_properties["max_winding_temperature_rise_c"]
        * degradation_ratio
        * (1.0 + temperature_stress)
    )

    pressures = {
        "mechanical_fatigue": guide_drag_factor,
        "contamination_ingress": sensitivity["contamination"] * contamination,
        "humidity_corrosion": sensitivity["humidity"] * humidity,
        "thermal_stress": sensitivity["temperature_stress"] * temperature_stress,
    }
    damage_breakdown = {"total": reported_damage}
    damage_breakdown.update(split_damage_by_pressure(reported_damage, pressures))

    rounded_torque_margin = round(torque_margin, 6)
    rounded_current_draw = round(current_draw_factor, 6)
    rounded_vibration = round(vibration_index, 6)

    return {
        "subsystem": component_config["subsystem"],
        "component": COMPONENT_NAME,
        "health": rounded_health,
        "status": status,
        "damage": damage_breakdown,
        "metrics": {
            "torque_margin": rounded_torque_margin,
            "current_draw_factor": rounded_current_draw,
            "vibration_index": rounded_vibration,
            "winding_temperature_rise_c": round(winding_temperature_rise_c, 6),
            "linear_guide_health": round(linear_guide_health, 6),
            "guide_drag_factor": round(guide_drag_factor, 6),
            "contamination_factor": round(contamination_factor, 6),
            "humidity_factor": round(humidity_factor, 6),
            "temperature_factor": round(temperature_factor, 6),
            "maintenance_factor": round(maintenance_factor, 6),
            "effective_load": round(effective_load, 6),
            "effective_age_delta": round(effective_age_delta, 10),
            "effective_age_cycles": round(effective_age_cycles, 10),
            "weibull_shape_beta": round(weibull_shape_beta, 6),
            "weibull_scale_cycles": round(weibull_scale_cycles, 6),
            "weibull_cumulative_hazard": round(cumulative_hazard, 10),
            "weibull_failure_probability": round(
                1.0 - rounded_health / initial_health,
                10,
            ),
        },
        "alerts": _build_alerts(
            status,
            rounded_torque_margin,
            rounded_current_draw,
            rounded_vibration,
            alerts_config,
        ),
    }
