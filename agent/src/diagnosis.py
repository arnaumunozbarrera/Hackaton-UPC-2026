from agent.src.health import (
    CRITICAL_HEALTH_THRESHOLD,
    DEGRADED_HEALTH_THRESHOLD,
    FAILED_HEALTH_THRESHOLD,
)
from agent.src.schemas import Diagnosis, Evidence, Severity


COMPONENT_DIAGNOSIS_PROFILES = {
    "heating_elements": {
        "issue": "thermal_instability",
        "description": "Heating elements are degrading under sustained temperature stress",
        "metrics": [
            "thermal_stability",
            "resistance_ohm",
            "energy_factor",
            "temperature_control_error_c",
            "effective_temperature_stress",
        ],
        "damage": [
            "thermal_overload",
            "electrical_degradation",
            "humidity_stress",
            "insulation_heat_loss",
        ],
        "drivers": ["temperature_stress", "humidity", "operational_load"],
    },
    "nozzle_plate": {
        "issue": "nozzle_clogging",
        "description": "Nozzle plate shows signs of clogging",
        "metrics": [
            "clogging_ratio",
            "blocked_nozzles_pct",
            "jetting_efficiency",
            "thermal_fatigue_index",
            "effective_contamination",
            "effective_temperature_stress",
        ],
        "damage": ["clogging", "thermal_fatigue"],
        "drivers": ["contamination", "humidity", "temperature_stress"],
    },
    "recoater_blade": {
        "issue": "recoater_wear",
        "description": "Recoater blade wear may increase powder contamination",
        "metrics": ["roughness_index", "thickness_mm", "wear_rate"],
        "damage": ["abrasive_wear", "contamination_damage", "humidity_damage"],
        "drivers": ["operational_load", "contamination", "humidity"],
    },
    "linear_guide": {
        "issue": "linear_guide_friction",
        "description": "Linear guide degradation is increasing friction and carriage drag",
        "metrics": [
            "friction_coefficient",
            "straightness_error_mm",
            "carriage_drag_factor",
            "alignment_score",
        ],
        "damage": ["rail_wear", "contamination_scoring", "humidity_corrosion"],
        "drivers": ["operational_load", "contamination", "humidity"],
    },
    "recoater_drive_motor": {
        "issue": "recoater_drive_motor_fatigue",
        "description": (
            "Recoater drive motor degradation is reducing torque margin "
            "and increasing vibration risk"
        ),
        "metrics": [
            "torque_margin",
            "current_draw_factor",
            "vibration_index",
            "winding_temperature_rise_c",
            "guide_drag_factor",
        ],
        "damage": [
            "mechanical_fatigue",
            "contamination_ingress",
            "humidity_corrosion",
            "thermal_stress",
        ],
        "drivers": [
            "operational_load",
            "temperature_stress",
            "contamination",
            "humidity",
        ],
    },
    "thermal_firing_resistors": {
        "issue": "firing_resistor_instability",
        "description": (
            "Thermal firing resistors are losing pulse uniformity "
            "and increasing misfire risk"
        ),
        "metrics": [
            "resistance_ohm",
            "pulse_uniformity",
            "misfire_risk",
            "firing_energy_factor",
            "effective_temperature_stress",
        ],
        "damage": [
            "electrical_fatigue",
            "thermal_fatigue",
            "humidity_stress",
            "contamination_deposits",
        ],
        "drivers": [
            "temperature_stress",
            "operational_load",
            "humidity",
            "contamination",
        ],
    },
    "cleaning_interface": {
        "issue": "cleaning_interface_degradation",
        "description": (
            "Cleaning interface degradation is reducing cleaning efficiency "
            "and increasing residue buildup"
        ),
        "metrics": [
            "cleaning_efficiency",
            "residue_buildup",
            "wiper_wear_ratio",
            "wipe_pressure_factor",
        ],
        "damage": ["mechanical_wear", "contamination_residue", "humidity_swelling"],
        "drivers": ["operational_load", "contamination", "humidity"],
    },
    "temperature_sensors": {
        "issue": "sensor_drift",
        "description": (
            "Temperature sensors show drift, slower response, "
            "or reduced calibration confidence"
        ),
        "metrics": [
            "drift_c",
            "response_time_ms",
            "signal_noise_index",
            "calibration_confidence",
        ],
        "damage": ["signal_aging", "thermal_drift", "humidity_corrosion"],
        "drivers": ["temperature_stress", "humidity", "operational_load"],
    },
    "insulation_panels": {
        "issue": "insulation_loss",
        "description": (
            "Insulation panel degradation is reducing thermal efficiency "
            "and increasing heat loss"
        ),
        "metrics": [
            "insulation_efficiency",
            "heat_loss_factor",
            "panel_integrity",
            "thermal_gradient_c",
        ],
        "damage": ["thermal_cycling", "humidity_absorption", "contamination_fouling"],
        "drivers": [
            "temperature_stress",
            "humidity",
            "contamination",
            "operational_load",
        ],
    },
}

DEFAULT_DIAGNOSIS_PROFILE = {
    "issue": "component_degradation",
    "description": "Component health or alerts indicate degradation requiring attention",
    "metrics": [],
    "damage": ["total"],
    "drivers": ["operational_load", "temperature_stress", "contamination", "humidity"],
}


def diagnose_latest(run_id: str, latest_record: dict) -> list[Diagnosis]:
    diagnoses: list[Diagnosis] = []

    components = latest_record["components"]
    drivers = latest_record["drivers"]
    timestamp = latest_record["timestamp"]

    for component_id, component in components.items():
        diagnosis = diagnose_component(
            run_id=run_id,
            timestamp=timestamp,
            component_id=component_id,
            component=component,
            drivers=drivers,
        )
        if diagnosis is not None:
            diagnoses.append(diagnosis)

    return diagnoses


def diagnose_component(
    run_id: str,
    timestamp: str,
    component_id: str,
    component: dict,
    drivers: dict,
) -> Diagnosis | None:
    health_index = component["health_index"]

    if not should_diagnose_component(component_id, component, drivers):
        return None

    profile = COMPONENT_DIAGNOSIS_PROFILES.get(component_id, DEFAULT_DIAGNOSIS_PROFILE)

    return Diagnosis(
        issue=profile["issue"],
        component_id=component_id,
        severity=severity_from_component(component),
        description=profile["description"],
        evidence=build_component_evidence(
            run_id=run_id,
            timestamp=timestamp,
            component_id=component_id,
            component=component,
            drivers=drivers,
            profile=profile,
        ),
    )


def should_diagnose_component(component_id: str, component: dict, drivers: dict) -> bool:
    health_index = component["health_index"]
    status = component.get("status", "UNKNOWN")
    alerts = component.get("alerts", [])

    if health_index < DEGRADED_HEALTH_THRESHOLD:
        return True

    if status in {"DEGRADED", "CRITICAL", "FAILED"}:
        return True

    if alerts:
        return True

    if component_id == "heating_elements":
        metrics = component.get("metrics", {})
        damage = component.get("damage", {})
        return is_heating_risk(
            health_index=health_index,
            temperature_stress=drivers.get("temperature_stress", 0.0),
            thermal_stability=metrics.get("thermal_stability"),
            thermal_overload=damage.get("thermal_overload", 0.0),
            electrical_degradation=damage.get("electrical_degradation", 0.0),
        )

    if component_id == "nozzle_plate":
        metrics = component.get("metrics", {})
        return (
            metrics.get("clogging_ratio", 0.0) > 0.55
            or metrics.get("blocked_nozzles_pct", 0.0) > 18.0
            or metrics.get("jetting_efficiency", 1.0) < 0.65
        )

    if component_id == "recoater_blade":
        return component.get("metrics", {}).get("roughness_index", 0.0) > 0.70

    return False


def is_heating_risk(
    health_index: float,
    temperature_stress: float,
    thermal_stability: float | None,
    thermal_overload: float,
    electrical_degradation: float,
) -> bool:
    if health_index < DEGRADED_HEALTH_THRESHOLD:
        return True

    if temperature_stress > 0.75 and health_index < 0.80:
        return True

    if (
        thermal_stability is not None
        and thermal_stability < 0.65
        and temperature_stress > 0.70
    ):
        return True

    if thermal_overload > 0.10 or electrical_degradation > 0.15:
        return True

    return False


def severity_from_health_index(health_index: float) -> Severity:
    if health_index < FAILED_HEALTH_THRESHOLD:
        return Severity.FAILED

    if health_index < CRITICAL_HEALTH_THRESHOLD:
        return Severity.CRITICAL

    if health_index < DEGRADED_HEALTH_THRESHOLD:
        return Severity.WARNING

    return Severity.WARNING


def severity_from_component(component: dict) -> Severity:
    status = component.get("status")

    if status == "FAILED":
        return Severity.FAILED

    if status == "CRITICAL":
        return Severity.CRITICAL

    severity = severity_from_health_index(component["health_index"])
    alert_severities = {
        alert.get("severity")
        for alert in component.get("alerts", [])
        if isinstance(alert, dict)
    }

    if "CRITICAL" in alert_severities and severity == Severity.WARNING:
        return Severity.CRITICAL

    return severity


def build_component_evidence(
    run_id: str,
    timestamp: str,
    component_id: str,
    component: dict,
    drivers: dict,
    profile: dict,
) -> list[Evidence]:
    evidence = [
        Evidence(
            run_id,
            timestamp,
            component_id,
            "health_index",
            component["health_index"],
        ),
        Evidence(
            run_id,
            timestamp,
            component_id,
            "status",
            component.get("status", "UNKNOWN"),
        ),
    ]

    for field in profile.get("drivers", []):
        if field in drivers:
            evidence.append(
                Evidence(run_id, timestamp, "machine", field, drivers[field])
            )

    metrics = component.get("metrics", {})
    for field in profile.get("metrics", []):
        if field in metrics and metrics[field] is not None:
            evidence.append(
                Evidence(run_id, timestamp, component_id, field, metrics[field])
            )

    damage = component.get("damage", {})
    for field in profile.get("damage", []):
        if field in damage and damage[field] is not None:
            evidence.append(
                Evidence(run_id, timestamp, component_id, field, damage[field])
            )

    alerts = component.get("alerts", [])
    if alerts:
        evidence.append(
            Evidence(run_id, timestamp, component_id, "alert_count", len(alerts))
        )
        for index, alert in enumerate(alerts[:3], start=1):
            if isinstance(alert, dict):
                if alert.get("severity"):
                    evidence.append(
                        Evidence(
                            run_id,
                            timestamp,
                            component_id,
                            f"alert_{index}_severity",
                            alert["severity"],
                        )
                    )
                if alert.get("code"):
                    evidence.append(
                        Evidence(
                            run_id,
                            timestamp,
                            component_id,
                            f"alert_{index}_code",
                            alert["code"],
                        )
                    )
            else:
                evidence.append(
                    Evidence(
                        run_id,
                        timestamp,
                        component_id,
                        f"alert_{index}",
                        alert,
                    )
                )

    return evidence
