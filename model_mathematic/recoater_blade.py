"""Recoater Blade degradation model.

The Recoater Blade model represents abrasive wear caused by repeated powder
spreading cycles. The base degradation rate is calibrated using a synthetic
target lifetime. Operational load increases wear linearly, contamination
amplifies abrasive damage, humidity worsens powder spreading conditions, and
maintenance reduces the effective degradation rate.
"""

from .common import (
    DAMAGE_PRECISION,
    HEALTH_PRECISION,
    clamp,
    deterministic_signed_noise,
    get_component_config,
    get_previous_health,
    get_simulation_seed,
    get_reported_damage,
    get_status_from_health,
    snap_health_to_failure_threshold,
    split_damage_by_pressure,
)


COMPONENT_NAME = "recoater_blade"


def _build_alerts(status, wear_rate, roughness_index, thickness_mm, alerts_config):
    alerts = []

    if wear_rate >= alerts_config["high_wear_rate_threshold"]:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "HIGH_WEAR_RATE",
                "message": "Recoater blade wear rate exceeds configured threshold.",
            }
        )

    if roughness_index >= alerts_config["high_roughness_threshold"]:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "HIGH_ROUGHNESS",
                "message": "Recoater blade roughness exceeds configured threshold.",
            }
        )

    if thickness_mm <= alerts_config["low_thickness_threshold_mm"]:
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "LOW_BLADE_THICKNESS",
                "message": "Recoater blade thickness is below configured threshold.",
            }
        )

    if status == "FAILED":
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "COMPONENT_FAILED",
                "message": "Recoater blade health is below the failure threshold.",
            }
        )

    return alerts


def calculate_recoater_blade_state(
    previous_state: dict,
    drivers: dict,
    config: dict,
) -> dict:
    """Calculate the deterministic Phase 1 state for the recoater blade."""
    component_config = get_component_config(config, COMPONENT_NAME)
    health_config = component_config["health"]
    calibration_config = component_config["calibration"]
    physical_properties = component_config["physical_properties"]
    sensitivity = component_config["sensitivity"]
    alerts_config = component_config["alerts"]
    uncertainty_config = component_config.get("uncertainty", {})

    previous_health = clamp(
        float(get_previous_health(previous_state, COMPONENT_NAME, health_config)),
        health_config["min"],
        health_config["max"],
    )

    drivers = drivers or {}

    operational_load = max(float(drivers.get("operational_load", 0.0)), 0.0)
    contamination = clamp(float(drivers.get("contamination", 0.0)), 0.0, 1.0)
    humidity = clamp(float(drivers.get("humidity", 0.0)), 0.0, 1.0)
    maintenance_level = clamp(float(drivers.get("maintenance_level", 0.0)), 0.0, 1.0)
    seed = get_simulation_seed(config)

    base_damage_per_cycle = (
        health_config["initial"] - calibration_config["failure_threshold"]
    ) / calibration_config["target_cycles_until_failure"]

    contamination_factor = 1.0 + sensitivity["contamination"] * contamination
    humidity_factor = 1.0 + sensitivity["humidity"] * humidity
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
        maintenance_level,
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

    physical_damage = (
        base_damage_per_cycle
        * operational_load ** sensitivity["load_exponent"]
        * contamination_factor
        * humidity_factor
        * maintenance_factor
    )
    uncertainty_damage = (
        base_damage_per_cycle
        * operational_load ** sensitivity["load_exponent"]
        * failure_risk_index
    )
    raw_damage = physical_damage + uncertainty_damage

    damage = clamp(
        raw_damage,
        0.0,
        previous_health - health_config["min"],
    )

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

    thickness_mm = max(
        physical_properties["min_thickness_mm"],
        physical_properties["initial_thickness_mm"] * rounded_health,
    )

    roughness_index = clamp(
        degradation_ratio * physical_properties["max_roughness_index"],
        0.0,
        physical_properties["max_roughness_index"],
    )

    wear_rate = reported_damage / max(operational_load, 1.0)

    pressures = {
        "abrasive_wear": 1.0,
        "contamination_damage": sensitivity["contamination"] * contamination,
        "humidity_damage": sensitivity["humidity"] * humidity,
        "maintenance_uncertainty": maintenance_error_index + failure_risk_index,
    }
    damage_breakdown = {"total": reported_damage}
    damage_breakdown.update(split_damage_by_pressure(reported_damage, pressures))

    rounded_thickness_mm = round(thickness_mm, 6)
    rounded_roughness_index = round(roughness_index, 6)
    rounded_wear_rate = round(wear_rate, 6)

    return {
        "subsystem": component_config["subsystem"],
        "component": COMPONENT_NAME,
        "health": rounded_health,
        "status": status,
        "damage": damage_breakdown,
        "metrics": {
            "thickness_mm": rounded_thickness_mm,
            "roughness_index": rounded_roughness_index,
            "wear_rate": rounded_wear_rate,
            "contamination_factor": round(contamination_factor, 6),
            "humidity_factor": round(humidity_factor, 6),
            "maintenance_factor": round(maintenance_factor, 6),
            "maintenance_error_index": round(maintenance_error_index, 6),
            "failure_risk_index": round(failure_risk_index, 6),
            "uncertainty_damage": round(uncertainty_damage, 8),
            "seed": seed,
        },
        "alerts": _build_alerts(
            status,
            rounded_wear_rate,
            rounded_roughness_index,
            rounded_thickness_mm,
            alerts_config,
        ),
    }
