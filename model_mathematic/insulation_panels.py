"""Insulation Panels degradation model for the thermal control subsystem."""

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


COMPONENT_NAME = "insulation_panels"


def _build_alerts(status, insulation_efficiency, heat_loss_factor, thermal_gradient_c, alerts_config):
    """Build threshold alerts for insulation efficiency and heat-loss behavior.

    @param status: Component status after the current degradation step.
    @param insulation_efficiency: Current normalized insulation efficiency.
    @param heat_loss_factor: Current normalized heat-loss factor.
    @param thermal_gradient_c: Current estimated thermal gradient in Celsius.
    @param alerts_config: Alert thresholds from the component configuration.
    @return: Alert dictionaries describing threshold breaches.
    """
    alerts = []

    if insulation_efficiency <= alerts_config["low_insulation_efficiency_threshold"]:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "LOW_INSULATION_EFFICIENCY",
                "message": "Insulation panel efficiency is below threshold.",
            }
        )

    if heat_loss_factor >= alerts_config["high_heat_loss_factor"]:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "HIGH_HEAT_LOSS",
                "message": "Insulation panel heat loss factor exceeds threshold.",
            }
        )

    if thermal_gradient_c >= alerts_config["high_thermal_gradient_c"]:
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "HIGH_THERMAL_GRADIENT",
                "message": "Thermal gradient across insulation exceeds threshold.",
            }
        )

    if status == "FAILED":
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "COMPONENT_FAILED",
                "message": "Insulation panels health is below the failure threshold.",
            }
        )

    return alerts


def calculate_insulation_panels_state(
    previous_state: dict,
    drivers: dict,
    config: dict,
) -> dict:
    """Calculate deterministic thermal cycling and insulation loss.

    @param previous_state: Previous insulation panel state or wrapped machine state.
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
    temperature_stress = clamp(float(drivers.get("temperature_stress", 0.0)), 0.0, 1.0)
    humidity = clamp(float(drivers.get("humidity", 0.0)), 0.0, 1.0)
    maintenance_level = clamp(float(drivers.get("maintenance_level", 0.0)), 0.0, 1.0)

    base_damage_per_cycle = (
        health_config["initial"] - calibration_config["failure_threshold"]
    ) / calibration_config["target_cycles_until_failure"]

    temperature_factor = 1.0 + sensitivity["temperature_stress"] * temperature_stress
    humidity_factor = 1.0 + sensitivity["humidity"] * humidity
    contamination_factor = 1.0 + sensitivity["contamination"] * contamination
    maintenance_factor = 1.0 - sensitivity["maintenance_protection"] * maintenance_level

    raw_damage = (
        base_damage_per_cycle
        * operational_load ** sensitivity["load_exponent"]
        * temperature_factor
        * humidity_factor
        * contamination_factor
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

    insulation_efficiency = clamp(
        1.0 - physical_properties["max_insulation_efficiency_loss"] * degradation_ratio,
        physical_properties["min_insulation_efficiency"],
        1.0,
    )
    heat_loss_factor = (
        1.0 + physical_properties["max_heat_loss_factor_increase"] * degradation_ratio
    )
    panel_integrity = clamp(1.0 - degradation_ratio, 0.0, 1.0)
    thermal_gradient_c = (
        physical_properties["max_thermal_gradient_c"]
        * degradation_ratio
        * (1.0 + temperature_stress)
    )

    pressures = {
        "thermal_cycling": 1.0 + sensitivity["temperature_stress"] * temperature_stress,
        "humidity_absorption": sensitivity["humidity"] * humidity,
        "contamination_fouling": sensitivity["contamination"] * contamination,
    }
    damage_breakdown = {"total": reported_damage}
    damage_breakdown.update(split_damage_by_pressure(reported_damage, pressures))

    rounded_efficiency = round(insulation_efficiency, 6)
    rounded_heat_loss = round(heat_loss_factor, 6)
    rounded_gradient = round(thermal_gradient_c, 6)

    return {
        "subsystem": component_config["subsystem"],
        "component": COMPONENT_NAME,
        "health": rounded_health,
        "status": status,
        "damage": damage_breakdown,
        "metrics": {
            "insulation_efficiency": rounded_efficiency,
            "heat_loss_factor": rounded_heat_loss,
            "panel_integrity": round(panel_integrity, 6),
            "thermal_gradient_c": rounded_gradient,
            "temperature_factor": round(temperature_factor, 6),
            "humidity_factor": round(humidity_factor, 6),
            "contamination_factor": round(contamination_factor, 6),
            "maintenance_factor": round(maintenance_factor, 6),
        },
        "alerts": _build_alerts(
            status,
            rounded_efficiency,
            rounded_heat_loss,
            rounded_gradient,
            alerts_config,
        ),
    }
