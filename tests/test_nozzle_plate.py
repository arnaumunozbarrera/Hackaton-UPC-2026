from model_mathematic.logic_engine import update_machine_state
from model_mathematic.nozzle_plate import calculate_nozzle_plate_state


CONFIG = {
    "components": {
        "recoater_blade": {
            "enabled": True,
            "subsystem": "recoating_system",
            "model_type": "linear_abrasive_wear",
            "health": {
                "initial": 1.0,
                "min": 0.0,
                "max": 1.0,
                "degraded_threshold": 0.70,
                "critical_threshold": 0.40,
                "failed_threshold": 0.10,
            },
            "calibration": {
                "target_cycles_until_failure": 1500,
                "failure_threshold": 0.10,
            },
            "physical_properties": {
                "initial_thickness_mm": 2.0,
                "min_thickness_mm": 0.25,
                "max_roughness_index": 1.0,
            },
            "sensitivity": {
                "contamination": 2.0,
                "humidity": 0.8,
                "maintenance_protection": 0.6,
                "load_exponent": 1.0,
            },
            "alerts": {
                "high_wear_rate_threshold": 0.003,
                "high_roughness_threshold": 0.70,
                "low_thickness_threshold_mm": 0.60,
            },
        },
        "nozzle_plate": {
            "enabled": True,
            "subsystem": "printhead_array",
            "model_type": "clogging_thermal_fatigue",
            "health": {
                "initial": 1.0,
                "min": 0.0,
                "max": 1.0,
                "degraded_threshold": 0.70,
                "critical_threshold": 0.40,
                "failed_threshold": 0.10,
            },
            "calibration": {
                "target_cycles_until_failure": 1200,
                "failure_threshold": 0.10,
            },
            "sensitivity": {
                "contamination": 3.0,
                "humidity": 1.2,
                "temperature_stress": 2.0,
                "maintenance_protection": 0.7,
                "load_exponent": 1.0,
                "recoater_cascade": 0.4,
            },
            "damage_weights": {
                "clogging": 0.65,
                "thermal_fatigue": 0.35,
            },
            "metrics": {
                "max_blocked_nozzles_pct": 100.0,
                "min_jetting_efficiency": 0.0,
                "jetting_efficiency_clogging_penalty": 0.5,
            },
            "alerts": {
                "high_clogging_threshold": 0.60,
                "high_thermal_fatigue_threshold": 0.60,
                "low_jetting_efficiency_threshold": 0.50,
            },
        },
    }
}


BASE_DRIVERS = {
    "operational_load": 10,
    "contamination": 0.30,
    "humidity": 0.45,
    "temperature_stress": 0.25,
    "maintenance_level": 0.80,
}


def test_output_structure():
    result = calculate_nozzle_plate_state(
        previous_state={"health": 1.0},
        drivers=BASE_DRIVERS,
        config=CONFIG,
        recoater_blade_state={"health": 1.0},
    )

    assert "subsystem" in result
    assert "component" in result
    assert "health" in result
    assert "status" in result
    assert "damage" in result
    assert "metrics" in result
    assert "alerts" in result


def test_deterministic_output_for_same_inputs():
    previous_state = {"health": 1.0}
    recoater_blade_state = {"health": 0.9}

    first = calculate_nozzle_plate_state(
        previous_state,
        BASE_DRIVERS,
        CONFIG,
        recoater_blade_state=recoater_blade_state,
    )

    second = calculate_nozzle_plate_state(
        previous_state,
        BASE_DRIVERS,
        CONFIG,
        recoater_blade_state=recoater_blade_state,
    )

    assert first == second


def test_operational_load_degrades_health():
    result = calculate_nozzle_plate_state(
        previous_state={"health": 1.0},
        drivers=BASE_DRIVERS,
        config=CONFIG,
        recoater_blade_state={"health": 1.0},
    )

    assert result["health"] < 1.0


def test_high_maintenance_reduces_damage():
    low_maintenance = {
        **BASE_DRIVERS,
        "maintenance_level": 0.0,
    }

    high_maintenance = {
        **BASE_DRIVERS,
        "maintenance_level": 1.0,
    }

    low_result = calculate_nozzle_plate_state(
        {"health": 1.0},
        low_maintenance,
        CONFIG,
        recoater_blade_state={"health": 1.0},
    )

    high_result = calculate_nozzle_plate_state(
        {"health": 1.0},
        high_maintenance,
        CONFIG,
        recoater_blade_state={"health": 1.0},
    )

    assert high_result["damage"]["total"] < low_result["damage"]["total"]


def test_high_contamination_increases_clogging_damage():
    low_contamination = {
        **BASE_DRIVERS,
        "contamination": 0.0,
    }

    high_contamination = {
        **BASE_DRIVERS,
        "contamination": 1.0,
    }

    low_result = calculate_nozzle_plate_state(
        {"health": 1.0},
        low_contamination,
        CONFIG,
        recoater_blade_state={"health": 1.0},
    )

    high_result = calculate_nozzle_plate_state(
        {"health": 1.0},
        high_contamination,
        CONFIG,
        recoater_blade_state={"health": 1.0},
    )

    assert high_result["damage"]["clogging"] > low_result["damage"]["clogging"]


def test_high_temperature_stress_increases_thermal_fatigue_damage():
    low_temperature_stress = {
        **BASE_DRIVERS,
        "temperature_stress": 0.0,
    }

    high_temperature_stress = {
        **BASE_DRIVERS,
        "temperature_stress": 1.0,
    }

    low_result = calculate_nozzle_plate_state(
        {"health": 1.0},
        low_temperature_stress,
        CONFIG,
        recoater_blade_state={"health": 1.0},
    )

    high_result = calculate_nozzle_plate_state(
        {"health": 1.0},
        high_temperature_stress,
        CONFIG,
        recoater_blade_state={"health": 1.0},
    )

    assert (
        high_result["damage"]["thermal_fatigue"]
        > low_result["damage"]["thermal_fatigue"]
    )


def test_degraded_recoater_blade_increases_effective_contamination_and_damage():
    healthy_recoater = {"health": 1.0}
    degraded_recoater = {"health": 0.25}

    healthy_result = calculate_nozzle_plate_state(
        {"health": 1.0},
        BASE_DRIVERS,
        CONFIG,
        recoater_blade_state=healthy_recoater,
    )

    degraded_result = calculate_nozzle_plate_state(
        {"health": 1.0},
        BASE_DRIVERS,
        CONFIG,
        recoater_blade_state=degraded_recoater,
    )

    assert (
        degraded_result["metrics"]["effective_contamination"]
        > healthy_result["metrics"]["effective_contamination"]
    )

    assert degraded_result["damage"]["total"] > healthy_result["damage"]["total"]


def test_driver_clamping_handles_out_of_range_inputs():
    result = calculate_nozzle_plate_state(
        {"health": 1.0},
        {
            "operational_load": -10,
            "contamination": 2.0,
            "humidity": 3.0,
            "temperature_stress": 4.0,
            "maintenance_level": 5.0,
        },
        CONFIG,
        recoater_blade_state={"health": -1.0},
    )

    assert result["health"] == 1.0
    assert result["damage"]["total"] == 0.0


def test_nominal_lifetime_reaches_failure_threshold_after_target_cycles():
    state = {"health": 1.0}

    drivers = {
        "operational_load": 1,
        "contamination": 0.0,
        "humidity": 0.0,
        "temperature_stress": 0.0,
        "maintenance_level": 0.0,
    }

    for _ in range(1200):
        state = calculate_nozzle_plate_state(
            state,
            drivers,
            CONFIG,
            recoater_blade_state={"health": 1.0},
        )

    assert state["health"] == 0.1
    assert state["status"] == "FAILED"


def test_reported_damage_matches_health_loss():
    previous_state = {"health": 0.02}

    drivers = {
        "operational_load": 10000,
        "contamination": 1.0,
        "humidity": 1.0,
        "temperature_stress": 1.0,
        "maintenance_level": 0.0,
    }

    result = calculate_nozzle_plate_state(
        previous_state,
        drivers,
        CONFIG,
        recoater_blade_state={"health": 0.1},
    )

    health_loss = previous_state["health"] - result["health"]

    assert result["damage"]["total"] == round(health_loss, 8)


def test_logic_engine_wraps_recoater_blade_and_nozzle_plate_states():
    result = update_machine_state(
        {
            "components": {
                "recoater_blade": {
                    "health": 1.0,
                },
                "nozzle_plate": {
                    "health": 1.0,
                },
            }
        },
        BASE_DRIVERS,
        CONFIG,
    )

    assert set(result.keys()) == {"components"}
    assert "recoater_blade" in result["components"]
    assert "nozzle_plate" in result["components"]
    assert result["components"]["nozzle_plate"]["component"] == "nozzle_plate"
