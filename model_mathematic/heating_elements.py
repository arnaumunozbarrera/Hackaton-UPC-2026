"""Heating Elements degradation model.

The Heating Elements model represents electrical degradation using an
exponential decay model. Operational load consumes useful life, temperature
stress accelerates degradation, humidity worsens the operating environment,
and maintenance reduces the effective damage.

This model is deterministic and belongs to Phase 1. It does not know about
timestamps, scenario IDs, run IDs, persistence, or simulation steps.
"""

import math

from .common import (
    DAMAGE_PRECISION,
    HEALTH_PRECISION,
    clamp,
    get_component_config,
    get_status_from_health,
    get_component_health,
    get_previous_health,
    get_reported_damage,
    snap_health_to_failure_threshold,
)


COMPONENT_NAME = "heating_elements"


def _build_alerts(
    status,
    resistance_ohm,
    energy_factor,
    thermal_stability,
    temperature_control_error_c,
    alerts_config,
):
    alerts = []

    if resistance_ohm >= alerts_config["high_resistance_threshold_ohm"]:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "HIGH_RESISTANCE",
                "message": "Heating element resistance exceeds configured threshold.",
            }
        )

    if energy_factor >= alerts_config["high_energy_factor_threshold"]:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "HIGH_ENERGY_CONSUMPTION",
                "message": "Heating elements require increased energy to maintain temperature.",
            }
        )

    if thermal_stability <= alerts_config["low_thermal_stability_threshold"]:
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "LOW_THERMAL_STABILITY",
                "message": "Thermal stability is below configured threshold.",
            }
        )

    if temperature_control_error_c >= alerts_config["high_temperature_control_error_c"]:
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "HIGH_TEMPERATURE_CONTROL_ERROR",
                "message": "Temperature control error exceeds configured threshold.",
            }
        )

    if status == "FAILED":
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "COMPONENT_FAILED",
                "message": "Heating elements health is below the failure threshold.",
            }
        )

    return alerts


def calculate_heating_elements_state(
    previous_state: dict,
    drivers: dict,
    config: dict,
    temperature_sensors_state: dict | None = None,
    insulation_panels_state: dict | None = None,
) -> dict:
    """Calculate the deterministic Phase 1 state for the heating elements.

    Required drivers:
        - operational_load: cycles/layers in this timestep
        - temperature_stress: normalized value from 0.0 to 1.0
        - humidity: normalized value from 0.0 to 1.0
        - maintenance_level: normalized value from 0.0 to 1.0
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
    temperature_stress = clamp(float(drivers.get("temperature_stress", 0.0)), 0.0, 1.0)
    humidity = clamp(float(drivers.get("humidity", 0.0)), 0.0, 1.0)
    maintenance_level = clamp(float(drivers.get("maintenance_level", 0.0)), 0.0, 1.0)

    temperature_sensors_health = get_component_health(temperature_sensors_state)
    insulation_panels_health = get_component_health(insulation_panels_state)
    sensor_degradation = 1.0 - temperature_sensors_health
    insulation_degradation = 1.0 - insulation_panels_health

    initial_health = health_config["initial"]
    failure_threshold = calibration_config["failure_threshold"]
    target_cycles_until_failure = calibration_config["target_cycles_until_failure"]

    decay_lambda = -math.log(failure_threshold / initial_health) / target_cycles_until_failure

    load_factor = operational_load ** sensitivity["load_exponent"]
    effective_temperature_stress = clamp(
        temperature_stress
        + sensitivity.get("temperature_sensor_cascade", 0.0) * sensor_degradation,
        0.0,
        1.0,
    )
    insulation_heat_loss_factor = (
        1.0 + sensitivity.get("insulation_cascade", 0.0) * insulation_degradation
    )

    temperature_factor = (
        1.0 + sensitivity["temperature_stress"] * effective_temperature_stress
    )
    humidity_factor = 1.0 + sensitivity["humidity"] * humidity
    maintenance_factor = 1.0 - sensitivity["maintenance_protection"] * maintenance_level

    effective_load = (
        load_factor
        * temperature_factor
        * humidity_factor
        * maintenance_factor
        * insulation_heat_loss_factor
    )

    raw_damage = previous_health * (1.0 - math.exp(-decay_lambda * effective_load))

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

    nominal_resistance_ohm = physical_properties["nominal_resistance_ohm"]
    max_resistance_increase_pct = physical_properties["max_resistance_increase_pct"]
    max_energy_overhead_factor = physical_properties["max_energy_overhead_factor"]
    max_temperature_control_error_c = physical_properties[
        "max_temperature_control_error_c"
    ]

    resistance_ohm = nominal_resistance_ohm * (
        1.0 + max_resistance_increase_pct * degradation_ratio
    )

    energy_factor = 1.0 + max_energy_overhead_factor * degradation_ratio

    thermal_stability = clamp(
        rounded_health * (1.0 - 0.3 * temperature_stress),
        0.0,
        1.0,
    )

    temperature_control_error_c = clamp(
        max_temperature_control_error_c
        * degradation_ratio
        * (1.0 + temperature_stress),
        0.0,
        max_temperature_control_error_c * 2.0,
    )

    electrical_pressure = 1.0
    thermal_pressure = sensitivity["temperature_stress"] * effective_temperature_stress
    humidity_pressure = sensitivity["humidity"] * humidity
    insulation_pressure = sensitivity.get("insulation_cascade", 0.0) * insulation_degradation

    total_pressure = (
        electrical_pressure
        + thermal_pressure
        + humidity_pressure
        + insulation_pressure
    )

    damage_breakdown = {
        "total": reported_damage,
        "electrical_degradation": round(
            reported_damage * electrical_pressure / total_pressure,
            DAMAGE_PRECISION,
        ),
        "thermal_overload": round(
            reported_damage * thermal_pressure / total_pressure,
            DAMAGE_PRECISION,
        ),
        "humidity_stress": round(
            reported_damage * humidity_pressure / total_pressure,
            DAMAGE_PRECISION,
        ),
        "insulation_heat_loss": round(
            reported_damage * insulation_pressure / total_pressure,
            DAMAGE_PRECISION,
        ),
    }

    rounded_resistance_ohm = round(resistance_ohm, 6)
    rounded_energy_factor = round(energy_factor, 6)
    rounded_thermal_stability = round(thermal_stability, 6)
    rounded_temperature_control_error_c = round(temperature_control_error_c, 6)

    return {
        "subsystem": component_config["subsystem"],
        "component": COMPONENT_NAME,
        "health": rounded_health,
        "status": status,
        "damage": damage_breakdown,
        "metrics": {
            "resistance_ohm": rounded_resistance_ohm,
            "energy_factor": rounded_energy_factor,
            "thermal_stability": rounded_thermal_stability,
            "temperature_control_error_c": rounded_temperature_control_error_c,
            "effective_temperature_stress": round(effective_temperature_stress, 6),
            "temperature_sensors_health": round(temperature_sensors_health, 6),
            "insulation_panels_health": round(insulation_panels_health, 6),
            "temperature_factor": round(temperature_factor, 6),
            "humidity_factor": round(humidity_factor, 6),
            "maintenance_factor": round(maintenance_factor, 6),
            "insulation_heat_loss_factor": round(insulation_heat_loss_factor, 6),
            "effective_load": round(effective_load, 6),
            "decay_lambda": round(decay_lambda, 10),
        },
        "alerts": _build_alerts(
            status=status,
            resistance_ohm=rounded_resistance_ohm,
            energy_factor=rounded_energy_factor,
            thermal_stability=rounded_thermal_stability,
            temperature_control_error_c=rounded_temperature_control_error_c,
            alerts_config=alerts_config,
        ),
    }
