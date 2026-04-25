from agent.src.schemas import Diagnosis, Evidence, Severity


def diagnose_latest(run_id: str, latest_record: dict) -> list[Diagnosis]:
    diagnoses: list[Diagnosis] = []

    components = latest_record["components"]
    drivers = latest_record["drivers"]
    timestamp = latest_record["timestamp"]

    heating = components.get("heating_elements")
    if heating is not None:
        thermal_stability = heating["metrics"].get("thermal_stability", 1.0)
        temperature_stress = drivers.get("temperature_stress", 1.0)
        health_index = heating["health_index"]

        if temperature_stress > 1.25 and thermal_stability < 0.75 and health_index < 0.60:
            diagnoses.append(
                Diagnosis(
                    issue="thermal_instability",
                    component_id="heating_elements",
                    severity=Severity.CRITICAL,
                    description="Heating elements are degrading under sustained temperature stress",
                    evidence=[
                        Evidence(run_id, timestamp, "heating_elements", "health_index", health_index),
                        Evidence(run_id, timestamp, "heating_elements", "thermal_stability", thermal_stability),
                        Evidence(run_id, timestamp, "machine", "temperature_stress", temperature_stress),
                    ],
                )
            )

    nozzle = components.get("nozzle_plate")
    if nozzle is not None:
        clogging_ratio = nozzle["metrics"].get("clogging_ratio", 0.0)
        blocked_nozzles_pct = nozzle["metrics"].get("blocked_nozzles_pct", 0.0)

        if clogging_ratio > 0.55 or blocked_nozzles_pct > 18.0:
            diagnoses.append(
                Diagnosis(
                    issue="nozzle_clogging",
                    component_id="nozzle_plate",
                    severity=Severity.WARNING,
                    description="Nozzle plate shows signs of clogging",
                    evidence=[
                        Evidence(run_id, timestamp, "nozzle_plate", "clogging_ratio", clogging_ratio),
                        Evidence(run_id, timestamp, "nozzle_plate", "blocked_nozzles_pct", blocked_nozzles_pct),
                    ],
                )
            )

    recoater = components.get("recoater_blade")
    if recoater is not None:
        roughness_index = recoater["metrics"].get("roughness_index", 0.0)
        health_index = recoater["health_index"]

        if roughness_index > 0.70 or health_index < 0.45:
            diagnoses.append(
                Diagnosis(
                    issue="recoater_wear",
                    component_id="recoater_blade",
                    severity=Severity.WARNING,
                    description="Recoater blade wear may increase powder contamination",
                    evidence=[
                        Evidence(run_id, timestamp, "recoater_blade", "health_index", health_index),
                        Evidence(run_id, timestamp, "recoater_blade", "roughness_index", roughness_index),
                    ],
                )
            )

    return diagnoses