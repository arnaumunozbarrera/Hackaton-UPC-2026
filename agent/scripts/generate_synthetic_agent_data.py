import json
from pathlib import Path


def build_record(step: int) -> dict:
    """Build one synthetic maintenance record for the demonstration scenario.

    @param step: Synthetic time step to encode in drivers and component state.
    @return: Historian-compatible record dictionary.
    """
    timestamp = f"2026-04-25T{step:02d}:00:00"

    heating_health = max(0.0, 0.95 - step * 0.035)
    nozzle_health = max(0.0, 0.98 - step * 0.018)
    recoater_health = max(0.0, 0.92 - step * 0.022)

    temperature_stress = 1.0 + step * 0.025
    contamination = 0.18 + step * 0.025
    operational_load = 0.72 + step * 0.01
    humidity = 0.45 + step * 0.008
    maintenance_level = max(0.0, 0.9 - step * 0.015)

    thermal_stability = max(0.0, 0.96 - step * 0.027)
    clogging_ratio = min(1.0, 0.08 + step * 0.032)
    blocked_nozzles_pct = min(100.0, 2.0 + step * 1.2)
    roughness_index = min(1.0, 0.22 + step * 0.027)

    return {
        "run_id": "synthetic_high_temperature_01",
        "timestamp": timestamp,
        "drivers": {
            "temperature_stress": round(temperature_stress, 4),
            "humidity": round(humidity, 4),
            "contamination": round(contamination, 4),
            "operational_load": round(operational_load, 4),
            "maintenance_level": round(maintenance_level, 4)
        },
        "components": {
            "recoater_blade": {
                "subsystem": "recoating_system",
                "health_index": round(recoater_health, 4),
                "status": status_from_health(recoater_health),
                "damage": {
                    "total": round(1.0 - recoater_health, 4),
                    "abrasive_wear": round((1.0 - recoater_health) * 0.78, 4),
                    "contamination_damage": round((1.0 - recoater_health) * 0.22, 4)
                },
                "metrics": {
                    "thickness_mm": round(1.8 - step * 0.012, 4),
                    "roughness_index": round(roughness_index, 4),
                    "wear_rate": round(0.0015 + step * 0.00018, 6)
                },
                "alerts": []
            },
            "nozzle_plate": {
                "subsystem": "printhead_array",
                "health_index": round(nozzle_health, 4),
                "status": status_from_health(nozzle_health),
                "damage": {
                    "total": round(1.0 - nozzle_health, 4),
                    "clogging": round((1.0 - nozzle_health) * 0.68, 4),
                    "thermal_fatigue": round((1.0 - nozzle_health) * 0.32, 4)
                },
                "metrics": {
                    "clogging_ratio": round(clogging_ratio, 4),
                    "blocked_nozzles_pct": round(blocked_nozzles_pct, 4),
                    "jetting_efficiency": round(max(0.0, 0.96 - clogging_ratio * 0.72), 4)
                },
                "alerts": []
            },
            "heating_elements": {
                "subsystem": "thermal_control",
                "health_index": round(heating_health, 4),
                "status": status_from_health(heating_health),
                "damage": {
                    "total": round(1.0 - heating_health, 4),
                    "electrical_degradation": round((1.0 - heating_health) * 0.74, 4),
                    "thermal_overload": round((1.0 - heating_health) * 0.26, 4)
                },
                "metrics": {
                    "resistance_ohm": round(10.0 + step * 0.085, 4),
                    "energy_factor": round(1.0 + step * 0.019, 4),
                    "thermal_stability": round(thermal_stability, 4)
                },
                "alerts": []
            }
        }
    }


def status_from_health(health: float) -> str:
    if health <= 0.05:
        return "FAILED"
    if health <= 0.30:
        return "CRITICAL"
    if health <= 0.70:
        return "DEGRADED"
    return "FUNCTIONAL"


def main() -> None:
    records = [build_record(step) for step in range(24)]
    output_path = Path("data/synthetic_agent_history.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=2)

    print(f"Generated {len(records)} records at {output_path}")


if __name__ == "__main__":
    main()
