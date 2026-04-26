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
    get_component_config,
    get_previous_health,
    get_reported_damage,
    get_status_from_health,
    snap_health_to_failure_threshold,
)


COMPONENT_NAME = "recoater_blade"


def _build_alerts(status, wear_rate, roughness_index, thickness_mm, alerts_config):
    """Build threshold alerts for visible recoater blade degradation.

    @param status: Component status after the current degradation step.
    @param wear_rate: Reported blade wear normalized by current operational load.
    @param roughness_index: Current blade roughness metric.
    @param thickness_mm: Current estimated blade thickness in millimeters.
    @param alerts_config: Alert thresholds from the component configuration.
    @return: Alert dictionaries describing threshold breaches.
    """
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
    """Calculate deterministic abrasive wear for the recoater blade.

    @param previous_state: Previous recoater blade state or wrapped machine state.
    @param drivers: Normalized operating drivers for the current simulation step.
    @param config: Phase 1 model configuration.
    @return: Component state containing health, status, damage, metrics, and alerts.
    """
    component_config = get_component_config(config, COMPONENT_NAME)
    health_config = component_config["health"]
    calibration_config = component_config["calibration"]
    physical_properties = component_config["physical_properties"]
    sensitivity = component_config["sensitivity"]
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
    maintenance_level = clamp(float(drivers.get("maintenance_level", 0.0)), 0.0, 1.0)

    base_damage_per_cycle = (
        health_config["initial"] - calibration_config["failure_threshold"]
    ) / calibration_config["target_cycles_until_failure"]

    contamination_factor = 1.0 + sensitivity["contamination"] * contamination
    humidity_factor = 1.0 + sensitivity["humidity"] * humidity
    maintenance_factor = 1.0 - sensitivity["maintenance_protection"] * maintenance_level

    raw_damage = (
        base_damage_per_cycle
        * operational_load ** sensitivity["load_exponent"]
        * contamination_factor
        * humidity_factor
        * maintenance_factor
    )

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

    abrasive_pressure = 1.0
    contamination_pressure = sensitivity["contamination"] * contamination
    humidity_pressure = sensitivity["humidity"] * humidity

    total_pressure = (
        abrasive_pressure
        + contamination_pressure
        + humidity_pressure
    )

    damage_breakdown = {
        "total": reported_damage,
        "abrasive_wear": round(
            reported_damage * abrasive_pressure / total_pressure,
            DAMAGE_PRECISION,
        ),
        "contamination_damage": round(
            reported_damage * contamination_pressure / total_pressure,
            DAMAGE_PRECISION,
        ),
        "humidity_damage": round(
            reported_damage * humidity_pressure / total_pressure,
            DAMAGE_PRECISION,
        ),
    }

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
        },
        "alerts": _build_alerts(
            status,
            rounded_wear_rate,
            rounded_roughness_index,
            rounded_thickness_mm,
            alerts_config,
        ),
    }
