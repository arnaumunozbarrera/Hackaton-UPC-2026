from model_mathematic.heating_elements import calculate_heating_elements_state
from model_mathematic.logic_engine import update_machine_state


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
                "heating_cascade": 0.3,
            },
            "damage_weights": {
                "clogging": 0.65,
                "thermal_fatigue": 0.35,
            },
            "metrics": {
                "max_blocked_nozzles_pct": 100.0,
                "min_jetting_efficiency": 0.0,
            },
            "alerts": {
                "high_clogging_threshold": 0.60,
                "high_thermal_fatigue_threshold": 0.60,
                "low_jetting_efficiency_threshold": 0.50,
            },
        },
        "heating_elements": {
            "enabled": True,
            "subsystem": "thermal_control",
            "model_type": "exponential_electrical_degradation",
            "health": {
                "initial": 1.0,
                "min": 0.0,
                "max": 1.0,
                "degraded_threshold": 0.70,
                "critical_threshold": 0.40,
                "failed_threshold": 0.10,
            },
            "calibration": {
                "target_cycles_until_failure": 2500,
                "failure_threshold": 0.10,
            },
            "sensitivity": {
                "temperature_stress": 2.0,
                "humidity": 0.6,
                "maintenance_protection": 0.5,
                "load_exponent": 1.0,
            },
            "physical_properties": {
                "nominal_resistance_ohm": 10.0,
                "max_resistance_increase_pct": 0.40,
                "max_energy_overhead_factor": 0.60,
                "max_temperature_control_error_c": 12.0,
            },
            "alerts": {
                "high_resistance_threshold_ohm": 13.0,
                "high_energy_factor_threshold": 1.35,
                "low_thermal_stability_threshold": 0.50,
                "high_temperature_control_error_c": 6.0,
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
    result = calculate_heating_elements_state(
        previous_state={"health": 1.0},
        drivers=BASE_DRIVERS,
        config=CONFIG,
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

    first = calculate_heating_elements_state(previous_state, BASE_DRIVERS, CONFIG)
    second = calculate_heating_elements_state(previous_state, BASE_DRIVERS, CONFIG)

    assert first == second


def test_operational_load_degrades_health():
    result = calculate_heating_elements_state(
        previous_state={"health": 1.0},
        drivers=BASE_DRIVERS,
        config=CONFIG,
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

    low_result = calculate_heating_elements_state(
        {"health": 1.0},
        low_maintenance,
        CONFIG,
    )

    high_result = calculate_heating_elements_state(
        {"health": 1.0},
        high_maintenance,
        CONFIG,
    )

    assert high_result["damage"]["total"] < low_result["damage"]["total"]


def test_high_temperature_stress_increases_damage():
    low_temperature_stress = {
        **BASE_DRIVERS,
        "temperature_stress": 0.0,
    }

    high_temperature_stress = {
        **BASE_DRIVERS,
        "temperature_stress": 1.0,
    }

    low_result = calculate_heating_elements_state(
        {"health": 1.0},
        low_temperature_stress,
        CONFIG,
    )

    high_result = calculate_heating_elements_state(
        {"health": 1.0},
        high_temperature_stress,
        CONFIG,
    )

    assert high_result["damage"]["total"] > low_result["damage"]["total"]
    assert (
        high_result["damage"]["thermal_overload"]
        > low_result["damage"]["thermal_overload"]
    )


def test_high_humidity_increases_damage():
    low_humidity = {
        **BASE_DRIVERS,
        "humidity": 0.0,
    }

    high_humidity = {
        **BASE_DRIVERS,
        "humidity": 1.0,
    }

    low_result = calculate_heating_elements_state(
        {"health": 1.0},
        low_humidity,
        CONFIG,
    )

    high_result = calculate_heating_elements_state(
        {"health": 1.0},
        high_humidity,
        CONFIG,
    )

    assert high_result["damage"]["total"] > low_result["damage"]["total"]
    assert high_result["damage"]["humidity_stress"] > low_result["damage"]["humidity_stress"]


def test_driver_clamping_handles_out_of_range_inputs():
    result = calculate_heating_elements_state(
        {"health": 1.0},
        {
            "operational_load": -10,
            "temperature_stress": 4.0,
            "humidity": 3.0,
            "maintenance_level": 5.0,
        },
        CONFIG,
    )

    assert result["health"] == 1.0
    assert result["damage"]["total"] == 0.0


def test_nominal_lifetime_reaches_failure_threshold_after_target_cycles():
    state = {"health": 1.0}

    drivers = {
        "operational_load": 1,
        "temperature_stress": 0.0,
        "humidity": 0.0,
        "maintenance_level": 0.0,
    }

    for _ in range(2500):
        state = calculate_heating_elements_state(state, drivers, CONFIG)

    assert abs(state["health"] - 0.1) <= 0.001
    assert state["status"] == "FAILED"


def test_reported_damage_matches_health_loss():
    previous_state = {"health": 0.02}

    drivers = {
        "operational_load": 10000,
        "temperature_stress": 1.0,
        "humidity": 1.0,
        "maintenance_level": 0.0,
    }

    result = calculate_heating_elements_state(
        previous_state,
        drivers,
        CONFIG,
    )

    health_loss = previous_state["health"] - result["health"]

    assert result["damage"]["total"] == round(health_loss, 8)


def test_metrics_reflect_degradation():
    result = calculate_heating_elements_state(
        previous_state={"health": 0.5},
        drivers=BASE_DRIVERS,
        config=CONFIG,
    )

    assert result["metrics"]["resistance_ohm"] > 10.0
    assert result["metrics"]["energy_factor"] > 1.0
    assert result["metrics"]["thermal_stability"] < 1.0
    assert result["metrics"]["temperature_control_error_c"] > 0.0


def test_zero_temperature_stress_reports_zero_thermal_overload():
    drivers = {
        "operational_load": 1,
        "temperature_stress": 0.0,
        "humidity": 0.5,
        "maintenance_level": 0.0,
    }

    result = calculate_heating_elements_state(
        {"health": 1.0},
        drivers,
        CONFIG,
    )

    assert result["damage"]["thermal_overload"] == 0.0


def test_zero_humidity_reports_zero_humidity_stress():
    drivers = {
        "operational_load": 1,
        "temperature_stress": 0.5,
        "humidity": 0.0,
        "maintenance_level": 0.0,
    }

    result = calculate_heating_elements_state(
        {"health": 1.0},
        drivers,
        CONFIG,
    )

    assert result["damage"]["humidity_stress"] == 0.0


def test_logic_engine_wraps_all_three_components():
    result = update_machine_state(
        {
            "components": {
                "recoater_blade": {
                    "health": 1.0,
                },
                "nozzle_plate": {
                    "health": 1.0,
                },
                "heating_elements": {
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
    assert "heating_elements" in result["components"]

    assert result["components"]["recoater_blade"]["component"] == "recoater_blade"
    assert result["components"]["nozzle_plate"]["component"] == "nozzle_plate"
    assert result["components"]["heating_elements"]["component"] == "heating_elements"


def test_logic_engine_passes_heating_state_to_nozzle_plate():
    result = update_machine_state(
        {
            "components": {
                "recoater_blade": {
                    "health": 1.0,
                },
                "nozzle_plate": {
                    "health": 1.0,
                },
                "heating_elements": {
                    "health": 0.2,
                },
            }
        },
        BASE_DRIVERS,
        CONFIG,
    )

    nozzle_state = result["components"]["nozzle_plate"]

    assert "effective_temperature_stress" in nozzle_state["metrics"]
    assert "heating_elements_health" in nozzle_state["metrics"]