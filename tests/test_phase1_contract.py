from pathlib import Path

import pytest
import yaml

from model_mathematic.heating_elements import calculate_heating_elements_state
from model_mathematic.logic_engine import update_machine_state
from model_mathematic.nozzle_plate import calculate_nozzle_plate_state
from model_mathematic.recoater_blade import calculate_recoater_blade_state


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "model_parameters.yaml"


def load_real_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def test_logic_engine_accepts_nozzle_plate_only_config():
    config = load_real_config()
    nozzle_only_config = {
        "components": {
            "nozzle_plate": config["components"]["nozzle_plate"],
        }
    }

    result = update_machine_state(
        previous_state={},
        drivers={
            "operational_load": 1,
            "contamination": 0.2,
            "humidity": 0.1,
            "temperature_stress": 0.3,
            "maintenance_level": 0.0,
        },
        config=nozzle_only_config,
    )

    assert set(result["components"]) == {"nozzle_plate"}
    assert (
        result["components"]["nozzle_plate"]["metrics"]["recoater_blade_health"]
        == 1.0
    )


def test_logic_engine_respects_enabled_false():
    config = load_real_config()
    config["components"]["nozzle_plate"]["enabled"] = False

    result = update_machine_state(
        previous_state={},
        drivers={
            "operational_load": 1,
            "contamination": 0.0,
            "humidity": 0.0,
            "temperature_stress": 0.0,
            "maintenance_level": 0.0,
        },
        config=config,
    )

    assert set(result["components"]) == {"heating_elements", "recoater_blade"}


def test_logic_engine_passes_updated_recoater_blade_state_to_nozzle_plate():
    config = load_real_config()
    previous_recoater_health = 0.25

    result = update_machine_state(
        previous_state={
            "components": {
                "recoater_blade": {"health": previous_recoater_health},
                "nozzle_plate": {"health": 1.0},
            }
        },
        drivers={
            "operational_load": 10,
            "contamination": 0.0,
            "humidity": 0.0,
            "temperature_stress": 0.0,
            "maintenance_level": 0.0,
        },
        config=config,
    )

    updated_recoater_health = result["components"]["recoater_blade"]["health"]
    nozzle_metrics = result["components"]["nozzle_plate"]["metrics"]

    assert updated_recoater_health < previous_recoater_health
    assert nozzle_metrics["recoater_blade_health"] == round(updated_recoater_health, 6)


def test_high_humidity_increases_nozzle_clogging_damage():
    config = load_real_config()
    base_drivers = {
        "operational_load": 1,
        "contamination": 0.4,
        "temperature_stress": 0.0,
        "maintenance_level": 0.0,
    }

    low_humidity = calculate_nozzle_plate_state(
        previous_state={"health": 1.0},
        drivers={**base_drivers, "humidity": 0.0},
        config=config,
        recoater_blade_state={"health": 1.0},
    )
    high_humidity = calculate_nozzle_plate_state(
        previous_state={"health": 1.0},
        drivers={**base_drivers, "humidity": 1.0},
        config=config,
        recoater_blade_state={"health": 1.0},
    )

    assert high_humidity["damage"]["clogging"] > low_humidity["damage"]["clogging"]


def test_recoater_physical_metrics_are_monotonic_with_health_loss():
    config = load_real_config()
    drivers = {
        "operational_load": 0,
        "contamination": 0.0,
        "humidity": 0.0,
        "maintenance_level": 0.0,
    }

    healthier = calculate_recoater_blade_state(
        previous_state={"health": 0.9},
        drivers=drivers,
        config=config,
    )
    more_degraded = calculate_recoater_blade_state(
        previous_state={"health": 0.4},
        drivers=drivers,
        config=config,
    )

    assert more_degraded["metrics"]["thickness_mm"] < healthier["metrics"]["thickness_mm"]
    assert more_degraded["metrics"]["roughness_index"] > healthier["metrics"]["roughness_index"]


def test_nozzle_jetting_efficiency_is_monotonic_with_health_and_clogging():
    config = load_real_config()
    drivers = {
        "operational_load": 0,
        "contamination": 0.0,
        "humidity": 0.0,
        "temperature_stress": 0.0,
        "maintenance_level": 0.0,
    }

    baseline = calculate_nozzle_plate_state(
        previous_state={"health": 0.9, "metrics": {"clogging_ratio": 0.1}},
        drivers=drivers,
        config=config,
        recoater_blade_state={"health": 1.0},
    )
    lower_health = calculate_nozzle_plate_state(
        previous_state={"health": 0.4, "metrics": {"clogging_ratio": 0.1}},
        drivers=drivers,
        config=config,
        recoater_blade_state={"health": 1.0},
    )
    higher_clogging = calculate_nozzle_plate_state(
        previous_state={"health": 0.9, "metrics": {"clogging_ratio": 0.6}},
        drivers=drivers,
        config=config,
        recoater_blade_state={"health": 1.0},
    )

    assert (
        lower_health["metrics"]["jetting_efficiency"]
        < baseline["metrics"]["jetting_efficiency"]
    )
    assert (
        higher_clogging["metrics"]["jetting_efficiency"]
        < baseline["metrics"]["jetting_efficiency"]
    )


def test_real_yaml_has_required_phase1_parameters_and_valid_ranges():
    config = load_real_config()
    components = config["components"]

    required_common_sections = {
        "enabled",
        "subsystem",
        "model_type",
        "health",
        "calibration",
        "sensitivity",
        "alerts",
    }
    assert required_common_sections <= set(components["recoater_blade"])
    assert required_common_sections <= set(components["nozzle_plate"])
    assert required_common_sections <= set(components["heating_elements"])
    assert {"physical_properties"} <= set(components["recoater_blade"])
    assert {"physical_properties"} <= set(components["heating_elements"])
    assert {"damage_weights", "metrics"} <= set(components["nozzle_plate"])

    for component_config in components.values():
        health = component_config["health"]
        calibration = component_config["calibration"]
        sensitivity = component_config["sensitivity"]

        assert calibration["target_cycles_until_failure"] > 0
        assert 0 <= calibration["failure_threshold"] < health["initial"] <= 1
        assert (
            health["failed_threshold"]
            < health["critical_threshold"]
            < health["degraded_threshold"]
            < health["initial"]
        )
        assert 1 - sensitivity["maintenance_protection"] >= 0

    nozzle_weights = components["nozzle_plate"]["damage_weights"]
    assert nozzle_weights["clogging"] + nozzle_weights[
        "thermal_fatigue"
    ] == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("component_name", "calculator", "drivers", "extra_kwargs"),
    [
        (
            "recoater_blade",
            calculate_recoater_blade_state,
            {
                "operational_load": 0.0001,
                "contamination": 0.0,
                "humidity": 0.0,
                "maintenance_level": 0.0,
            },
            {},
        ),
        (
            "nozzle_plate",
            calculate_nozzle_plate_state,
            {
                "operational_load": 0.0001,
                "contamination": 0.0,
                "humidity": 0.0,
                "temperature_stress": 0.0,
                "maintenance_level": 0.0,
            },
            {"recoater_blade_state": {"health": 1.0}},
        ),
        (
            "heating_elements",
            calculate_heating_elements_state,
            {
                "operational_load": 0.0001,
                "temperature_stress": 0.0,
                "humidity": 0.0,
                "maintenance_level": 0.0,
            },
            {},
        ),
    ],
)
def test_health_precision_matches_reported_damage_for_small_loads(
    component_name,
    calculator,
    drivers,
    extra_kwargs,
):
    config = load_real_config()
    previous_state = {"health": 1.0}

    result = calculator(
        previous_state=previous_state,
        drivers=drivers,
        config=config,
        **extra_kwargs,
    )

    health_loss = round(previous_state["health"] - result["health"], 8)

    assert result["damage"]["total"] > 0
    assert result["damage"]["total"] == health_loss
