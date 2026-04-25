import json
from pathlib import Path


def status_from_health(health: float) -> str:
    if health <= 0.05:
        return "FAILED"
    if health <= 0.30:
        return "CRITICAL"
    if health <= 0.70:
        return "DEGRADED"
    return "FUNCTIONAL"


def build_record(
    run_id: str,
    step: int,
    heating_decay: float,
    nozzle_decay: float,
    recoater_decay: float,
    temperature_base: float,
    temperature_growth: float,
    contamination_base: float,
    contamination_growth: float,
    load_base: float,
    load_growth: float,
    humidity_base: float,
    humidity_growth: float,
    maintenance_base: float,
    maintenance_decay: float,
    clogging_base: float,
    clogging_growth: float,
    roughness_base: float,
    roughness_growth: float,
    thermal_stability_base: float,
    thermal_stability_decay: float,
) -> dict:
    timestamp = f"2026-04-25T{step:02d}:00:00"

    heating_health = max(0.0, 0.95 - step * heating_decay)
    nozzle_health = max(0.0, 0.98 - step * nozzle_decay)
    recoater_health = max(0.0, 0.92 - step * recoater_decay)

    temperature_stress = temperature_base + step * temperature_growth
    contamination = contamination_base + step * contamination_growth
    operational_load = load_base + step * load_growth
    humidity = humidity_base + step * humidity_growth
    maintenance_level = max(0.0, maintenance_base - step * maintenance_decay)

    thermal_stability = max(0.0, thermal_stability_base - step * thermal_stability_decay)
    clogging_ratio = min(1.0, clogging_base + step * clogging_growth)
    blocked_nozzles_pct = min(100.0, 2.0 + clogging_ratio * 34.0)
    roughness_index = min(1.0, roughness_base + step * roughness_growth)

    return {
        "run_id": run_id,
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
                    "thickness_mm": round(1.8 - step * recoater_decay * 0.55, 4),
                    "roughness_index": round(roughness_index, 4),
                    "wear_rate": round(0.001 + step * recoater_decay * 0.009, 6)
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
                    "resistance_ohm": round(10.0 + step * heating_decay * 2.4, 4),
                    "energy_factor": round(1.0 + step * heating_decay * 0.5, 4),
                    "thermal_stability": round(thermal_stability, 4)
                },
                "alerts": []
            }
        }
    }


def build_scenario(run_id: str, config: dict, steps: int = 24) -> list[dict]:
    return [
        build_record(run_id=run_id, step=step, **config)
        for step in range(steps)
    ]


def main() -> None:
    scenarios = {
        "normal_operation": {
            "heating_decay": 0.004,
            "nozzle_decay": 0.003,
            "recoater_decay": 0.003,
            "temperature_base": 1.00,
            "temperature_growth": 0.002,
            "contamination_base": 0.12,
            "contamination_growth": 0.003,
            "load_base": 0.55,
            "load_growth": 0.001,
            "humidity_base": 0.42,
            "humidity_growth": 0.001,
            "maintenance_base": 0.95,
            "maintenance_decay": 0.002,
            "clogging_base": 0.05,
            "clogging_growth": 0.004,
            "roughness_base": 0.15,
            "roughness_growth": 0.004,
            "thermal_stability_base": 0.96,
            "thermal_stability_decay": 0.004
        },
        "mild_nozzle_clogging": {
            "heating_decay": 0.006,
            "nozzle_decay": 0.012,
            "recoater_decay": 0.005,
            "temperature_base": 1.04,
            "temperature_growth": 0.004,
            "contamination_base": 0.20,
            "contamination_growth": 0.009,
            "load_base": 0.62,
            "load_growth": 0.003,
            "humidity_base": 0.48,
            "humidity_growth": 0.003,
            "maintenance_base": 0.88,
            "maintenance_decay": 0.006,
            "clogging_base": 0.16,
            "clogging_growth": 0.018,
            "roughness_base": 0.20,
            "roughness_growth": 0.008,
            "thermal_stability_base": 0.94,
            "thermal_stability_decay": 0.006
        },
        "thermal_risk": {
            "heating_decay": 0.020,
            "nozzle_decay": 0.010,
            "recoater_decay": 0.006,
            "temperature_base": 1.10,
            "temperature_growth": 0.015,
            "contamination_base": 0.16,
            "contamination_growth": 0.006,
            "load_base": 0.72,
            "load_growth": 0.008,
            "humidity_base": 0.43,
            "humidity_growth": 0.002,
            "maintenance_base": 0.86,
            "maintenance_decay": 0.009,
            "clogging_base": 0.10,
            "clogging_growth": 0.012,
            "roughness_base": 0.22,
            "roughness_growth": 0.007,
            "thermal_stability_base": 0.92,
            "thermal_stability_decay": 0.018
        },
        "severe_thermal_risk": {
            "heating_decay": 0.035,
            "nozzle_decay": 0.018,
            "recoater_decay": 0.022,
            "temperature_base": 1.00,
            "temperature_growth": 0.025,
            "contamination_base": 0.18,
            "contamination_growth": 0.025,
            "load_base": 0.72,
            "load_growth": 0.010,
            "humidity_base": 0.45,
            "humidity_growth": 0.008,
            "maintenance_base": 0.90,
            "maintenance_decay": 0.015,
            "clogging_base": 0.08,
            "clogging_growth": 0.032,
            "roughness_base": 0.22,
            "roughness_growth": 0.027,
            "thermal_stability_base": 0.96,
            "thermal_stability_decay": 0.027
        },
        "recoater_near_failure": {
            "heating_decay": 0.008,
            "nozzle_decay": 0.010,
            "recoater_decay": 0.030,
            "temperature_base": 1.03,
            "temperature_growth": 0.006,
            "contamination_base": 0.22,
            "contamination_growth": 0.020,
            "load_base": 0.68,
            "load_growth": 0.006,
            "humidity_base": 0.44,
            "humidity_growth": 0.004,
            "maintenance_base": 0.82,
            "maintenance_decay": 0.010,
            "clogging_base": 0.12,
            "clogging_growth": 0.016,
            "roughness_base": 0.32,
            "roughness_growth": 0.030,
            "thermal_stability_base": 0.94,
            "thermal_stability_decay": 0.007
        }
    }

    output_dir = Path("data/agent_scenarios")
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, config in scenarios.items():
        run_id = f"synthetic_{name}_01"
        records = build_scenario(run_id, config)
        output_path = output_dir / f"{name}.json"

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(records, file, indent=2)

        print(f"Generated {len(records)} records at {output_path}")


if __name__ == "__main__":
    main()