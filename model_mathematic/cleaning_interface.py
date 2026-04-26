"""Cleaning Interface degradation model for the printhead array."""

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


COMPONENT_NAME = "cleaning_interface"


def _build_alerts(status, cleaning_efficiency, residue_buildup, wipe_pressure_factor, alerts_config):
    """Build threshold alerts for cleaning efficiency and residue accumulation.

    @param status: Component status after the current degradation step.
    @param cleaning_efficiency: Current normalized cleaning efficiency.
    @param residue_buildup: Current normalized residue buildup.
    @param wipe_pressure_factor: Current normalized wipe pressure factor.
    @param alerts_config: Alert thresholds from the component configuration.
    @return: Alert dictionaries describing threshold breaches.
    """
    alerts = []

    if cleaning_efficiency <= alerts_config["low_cleaning_efficiency_threshold"]:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "LOW_CLEANING_EFFICIENCY",
                "message": "Printhead cleaning interface efficiency is below threshold.",
            }
        )

    if residue_buildup >= alerts_config["high_residue_buildup_threshold"]:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "HIGH_RESIDUE_BUILDUP",
                "message": "Cleaning interface residue buildup exceeds threshold.",
            }
        )

    if wipe_pressure_factor <= alerts_config["low_wipe_pressure_factor"]:
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "LOW_WIPE_PRESSURE",
                "message": "Cleaning interface wipe pressure is below threshold.",
            }
        )

    if status == "FAILED":
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "COMPONENT_FAILED",
                "message": "Cleaning interface health is below the failure threshold.",
            }
        )

    return alerts


def calculate_cleaning_interface_state(
    previous_state: dict,
    drivers: dict,
    config: dict,
) -> dict:
    """Calculate deterministic wiper wear and residue accumulation.

    @param previous_state: Previous cleaning interface state or wrapped machine state.
    @param drivers: Normalized operating drivers for the current simulation step.
    @param config: Phase 1 model configuration.
    @return: Component state containing health, status, damage, metrics, and alerts.
    """
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

    cleaning_efficiency = clamp(
        1.0 - physical_properties["max_cleaning_efficiency_loss"] * degradation_ratio,
        physical_properties["min_cleaning_efficiency"],
        1.0,
    )
    residue_buildup = clamp(
        physical_properties["max_residue_buildup"] * degradation_ratio
        + physical_properties["current_contamination_residue_gain"] * contamination,
        0.0,
        physical_properties["max_residue_buildup"],
    )
    wiper_wear_ratio = clamp(degradation_ratio, 0.0, 1.0)
    wipe_pressure_factor = clamp(
        1.0 - physical_properties["max_wipe_pressure_loss"] * degradation_ratio,
        0.0,
        1.0,
    )

    pressures = {
        "mechanical_wear": 1.0,
        "contamination_residue": sensitivity["contamination"] * contamination,
        "humidity_swelling": sensitivity["humidity"] * humidity,
    }
    damage_breakdown = {"total": reported_damage}
    damage_breakdown.update(split_damage_by_pressure(reported_damage, pressures))

    rounded_efficiency = round(cleaning_efficiency, 6)
    rounded_residue = round(residue_buildup, 6)
    rounded_pressure = round(wipe_pressure_factor, 6)

    return {
        "subsystem": component_config["subsystem"],
        "component": COMPONENT_NAME,
        "health": rounded_health,
        "status": status,
        "damage": damage_breakdown,
        "metrics": {
            "cleaning_efficiency": rounded_efficiency,
            "residue_buildup": rounded_residue,
            "wiper_wear_ratio": round(wiper_wear_ratio, 6),
            "wipe_pressure_factor": rounded_pressure,
            "contamination_factor": round(contamination_factor, 6),
            "humidity_factor": round(humidity_factor, 6),
            "maintenance_factor": round(maintenance_factor, 6),
        },
        "alerts": _build_alerts(
            status,
            rounded_efficiency,
            rounded_residue,
            rounded_pressure,
            alerts_config,
        ),
    }
