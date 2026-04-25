from model_mathematic.common import get_status_from_health
from model_mathematic.logic_engine import update_machine_state
from model_mathematic.recoater_blade import calculate_recoater_blade_state


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
        }
    }
}


BASE_DRIVERS = {
    "operational_load": 10,
    "contamination": 0.30,
    "humidity": 0.45,
    "maintenance_level": 0.80,
}


def test_output_structure():
    result = calculate_recoater_blade_state({"health": 1.0}, BASE_DRIVERS, CONFIG)

    assert "subsystem" in result
    assert "component" in result
    assert "health" in result
    assert "status" in result
    assert "damage" in result
    assert "metrics" in result
    assert "alerts" in result


def test_deterministic_output_for_same_inputs():
    previous_state = {"health": 1.0}

    first = calculate_recoater_blade_state(previous_state, BASE_DRIVERS, CONFIG)
    second = calculate_recoater_blade_state(previous_state, BASE_DRIVERS, CONFIG)

    assert first == second


def test_operational_load_degrades_health():
    result = calculate_recoater_blade_state({"health": 1.0}, BASE_DRIVERS, CONFIG)

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

    low_result = calculate_recoater_blade_state({"health": 1.0}, low_maintenance, CONFIG)
    high_result = calculate_recoater_blade_state(
        {"health": 1.0}, high_maintenance, CONFIG
    )

    assert high_result["damage"]["total"] < low_result["damage"]["total"]


def test_high_contamination_increases_damage():
    low_contamination = {
        **BASE_DRIVERS,
        "contamination": 0.0,
    }
    high_contamination = {
        **BASE_DRIVERS,
        "contamination": 1.0,
    }

    low_result = calculate_recoater_blade_state(
        {"health": 1.0}, low_contamination, CONFIG
    )
    high_result = calculate_recoater_blade_state(
        {"health": 1.0}, high_contamination, CONFIG
    )

    assert high_result["damage"]["total"] > low_result["damage"]["total"]


def test_driver_clamping_handles_out_of_range_inputs():
    result = calculate_recoater_blade_state(
        {"health": 1.0},
        {
            "operational_load": -10,
            "contamination": 2.0,
            "humidity": 3.0,
            "maintenance_level": 4.0,
        },
        CONFIG,
    )

    assert result["health"] == 1.0
    assert result["damage"]["total"] == 0.0
    assert result["metrics"]["wear_rate"] == 0.0


def test_status_thresholds():
    health_config = CONFIG["components"]["recoater_blade"]["health"]

    assert get_status_from_health(0.8, health_config) == "FUNCTIONAL"
    assert get_status_from_health(0.6, health_config) == "DEGRADED"
    assert get_status_from_health(0.3, health_config) == "CRITICAL"
    assert get_status_from_health(0.05, health_config) == "FAILED"


def test_logic_engine_wraps_recoater_blade_state():
    result = update_machine_state(
        {
            "components": {
                "recoater_blade": {
                    "health": 1.0,
                }
            }
        },
        BASE_DRIVERS,
        CONFIG,
    )

    assert set(result.keys()) == {"components"}
    assert "recoater_blade" in result["components"]
    assert result["components"]["recoater_blade"]["component"] == "recoater_blade"

def test_nominal_lifetime_reaches_failure_threshold_after_target_cycles():
    state = {"health": 1.0}
    drivers = {
        "operational_load": 1,
        "contamination": 0.0,
        "humidity": 0.0,
        "maintenance_level": 0.0,
    }

    for _ in range(1500):
        state = calculate_recoater_blade_state(state, drivers, CONFIG)

    assert state["health"] == 0.1
    assert state["status"] == "FAILED"

def test_reported_damage_matches_health_loss():
    previous_state = {"health": 0.02}
    drivers = {
        "operational_load": 10000,
        "contamination": 1.0,
        "humidity": 1.0,
        "maintenance_level": 0.0,
    }

    result = calculate_recoater_blade_state(previous_state, drivers, CONFIG)

    health_loss = previous_state["health"] - result["health"]

    assert result["damage"]["total"] == round(health_loss, 8)

def test_zero_contamination_reports_zero_contamination_damage():
    drivers = {
        "operational_load": 1,
        "contamination": 0.0,
        "humidity": 0.5,
        "maintenance_level": 0.0,
    }

    result = calculate_recoater_blade_state({"health": 1.0}, drivers, CONFIG)

    assert result["damage"]["contamination_damage"] == 0.0


def test_zero_humidity_reports_zero_humidity_damage():
    drivers = {
        "operational_load": 1,
        "contamination": 0.5,
        "humidity": 0.0,
        "maintenance_level": 0.0,
    }

    result = calculate_recoater_blade_state({"health": 1.0}, drivers, CONFIG)

    assert result["damage"]["humidity_damage"] == 0.0
