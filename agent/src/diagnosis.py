from agent.src.health import CRITICAL_HEALTH_THRESHOLD, DEGRADED_HEALTH_THRESHOLD, FAILED_HEALTH_THRESHOLD
from agent.src.schemas import Diagnosis, Evidence, Severity


def diagnose_latest(run_id: str, latest_record: dict) -> list[Diagnosis]:
    diagnoses: list[Diagnosis] = []

    components = latest_record["components"]
    drivers = latest_record["drivers"]
    timestamp = latest_record["timestamp"]

    heating = components.get("heating_elements")
    if heating is not None:
        thermal_stability = heating.get("metrics", {}).get("thermal_stability")
        temperature_stress = drivers.get("temperature_stress", 0.0)
        health_index = heating["health_index"]
        thermal_overload = heating.get("damage", {}).get("thermal_overload", 0.0)
        electrical_degradation = heating.get("damage", {}).get("electrical_degradation", 0.0)

        if is_heating_risk(
            health_index=health_index,
            temperature_stress=temperature_stress,
            thermal_stability=thermal_stability,
            thermal_overload=thermal_overload,
            electrical_degradation=electrical_degradation,
        ):
            diagnoses.append(
                Diagnosis(
                    issue="thermal_instability",
                    component_id="heating_elements",
                    severity=severity_from_health_index(health_index),
                    description="Heating elements are degrading under sustained temperature stress",
                    evidence=build_heating_evidence(
                        run_id=run_id,
                        timestamp=timestamp,
                        health_index=health_index,
                        thermal_stability=thermal_stability,
                        temperature_stress=temperature_stress,
                        thermal_overload=thermal_overload,
                        electrical_degradation=electrical_degradation,
                    ),
                )
            )

    nozzle = components.get("nozzle_plate")
    if nozzle is not None:
        health_index = nozzle["health_index"]
        clogging_ratio = nozzle.get("metrics", {}).get("clogging_ratio", 0.0)
        blocked_nozzles_pct = nozzle.get("metrics", {}).get("blocked_nozzles_pct", 0.0)
        clogging_damage = nozzle.get("damage", {}).get("clogging", 0.0)

        if health_index < DEGRADED_HEALTH_THRESHOLD or clogging_ratio > 0.55 or blocked_nozzles_pct > 18.0:
            diagnoses.append(
                Diagnosis(
                    issue="nozzle_clogging",
                    component_id="nozzle_plate",
                    severity=severity_from_health_index(health_index),
                    description="Nozzle plate shows signs of clogging",
                    evidence=[
                        Evidence(run_id, timestamp, "nozzle_plate", "health_index", health_index),
                        Evidence(run_id, timestamp, "nozzle_plate", "clogging_ratio", clogging_ratio),
                        Evidence(run_id, timestamp, "nozzle_plate", "blocked_nozzles_pct", blocked_nozzles_pct),
                        Evidence(run_id, timestamp, "nozzle_plate", "clogging_damage", clogging_damage),
                    ],
                )
            )

    recoater = components.get("recoater_blade")
    if recoater is not None:
        health_index = recoater["health_index"]
        roughness_index = recoater.get("metrics", {}).get("roughness_index", 0.0)
        abrasive_wear = recoater.get("damage", {}).get("abrasive_wear", 0.0)
        contamination_damage = recoater.get("damage", {}).get("contamination_damage", 0.0)

        if health_index < DEGRADED_HEALTH_THRESHOLD or roughness_index > 0.70:
            diagnoses.append(
                Diagnosis(
                    issue="recoater_wear",
                    component_id="recoater_blade",
                    severity=severity_from_health_index(health_index),
                    description="Recoater blade wear may increase powder contamination",
                    evidence=[
                        Evidence(run_id, timestamp, "recoater_blade", "health_index", health_index),
                        Evidence(run_id, timestamp, "recoater_blade", "roughness_index", roughness_index),
                        Evidence(run_id, timestamp, "recoater_blade", "abrasive_wear", abrasive_wear),
                        Evidence(run_id, timestamp, "recoater_blade", "contamination_damage", contamination_damage),
                    ],
                )
            )

    return diagnoses


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

    if thermal_stability is not None and thermal_stability < 0.65 and temperature_stress > 0.70:
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


def build_heating_evidence(
    run_id: str,
    timestamp: str,
    health_index: float,
    thermal_stability: float | None,
    temperature_stress: float,
    thermal_overload: float,
    electrical_degradation: float,
) -> list[Evidence]:
    evidence = [
        Evidence(run_id, timestamp, "heating_elements", "health_index", health_index),
        Evidence(run_id, timestamp, "machine", "temperature_stress", temperature_stress),
        Evidence(run_id, timestamp, "heating_elements", "thermal_overload", thermal_overload),
        Evidence(run_id, timestamp, "heating_elements", "electrical_degradation", electrical_degradation),
    ]

    if thermal_stability is not None:
        evidence.append(
            Evidence(run_id, timestamp, "heating_elements", "thermal_stability", thermal_stability)
        )

    return evidence