import copy
from pathlib import Path

import pytest
import yaml

from model_mathematic.heating_elements import calculate_heating_elements_state
from model_mathematic.nozzle_plate import calculate_nozzle_plate_state
from model_mathematic.recoater_blade import calculate_recoater_blade_state
from model_mathematic.recoater_drive_motor import calculate_recoater_drive_motor_state


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "model_parameters.yaml"


def load_real_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def _seeded_config(seed: int) -> dict:
    config = load_real_config()
    config["seed"] = seed
    for component_name in (
        "recoater_blade",
        "recoater_drive_motor",
        "nozzle_plate",
    ):
        config["components"][component_name]["uncertainty"] = {
            "maintenance_error_rate": 0.12,
            "failure_risk_scale": 0.08,
        }
    return config


@pytest.mark.parametrize(
    ("component_name", "calculator", "kwargs", "drivers"),
    [
        (
            "recoater_blade",
            calculate_recoater_blade_state,
            {},
            {
                "operational_load": 12,
                "contamination": 0.45,
                "humidity": 0.35,
                "maintenance_level": 0.25,
            },
        ),
        (
            "recoater_drive_motor",
            calculate_recoater_drive_motor_state,
            {"linear_guide_state": {"health": 0.82}},
            {
                "operational_load": 12,
                "contamination": 0.45,
                "humidity": 0.35,
                "temperature_stress": 0.28,
                "maintenance_level": 0.25,
            },
        ),
        (
            "nozzle_plate",
            calculate_nozzle_plate_state,
            {
                "recoater_blade_state": {"health": 0.91},
                "heating_elements_state": {"health": 0.93},
                "cleaning_interface_state": {"health": 0.88},
                "thermal_firing_resistors_state": {"health": 0.89},
            },
            {
                "operational_load": 12,
                "contamination": 0.45,
                "humidity": 0.35,
                "temperature_stress": 0.28,
                "maintenance_level": 0.25,
            },
        ),
    ],
)
def test_seeded_uncertainty_is_reproducible_for_same_seed(
    component_name,
    calculator,
    kwargs,
    drivers,
):
    config = _seeded_config(1234)
    previous_state = {"health": 0.92}

    first = calculator(
        previous_state=copy.deepcopy(previous_state),
        drivers=copy.deepcopy(drivers),
        config=copy.deepcopy(config),
        **copy.deepcopy(kwargs),
    )
    second = calculator(
        previous_state=copy.deepcopy(previous_state),
        drivers=copy.deepcopy(drivers),
        config=copy.deepcopy(config),
        **copy.deepcopy(kwargs),
    )

    assert first == second
    assert "failure_risk_index" in first["metrics"]
    assert "maintenance_error_index" in first["metrics"]
    assert first["metrics"]["failure_risk_index"] >= 0.0
    assert first["metrics"]["maintenance_error_index"] >= 0.0


@pytest.mark.parametrize(
    ("component_name", "calculator", "kwargs", "drivers"),
    [
        (
            "recoater_blade",
            calculate_recoater_blade_state,
            {},
            {
                "operational_load": 12,
                "contamination": 0.45,
                "humidity": 0.35,
                "maintenance_level": 0.25,
            },
        ),
        (
            "recoater_drive_motor",
            calculate_recoater_drive_motor_state,
            {"linear_guide_state": {"health": 0.82}},
            {
                "operational_load": 12,
                "contamination": 0.45,
                "humidity": 0.35,
                "temperature_stress": 0.28,
                "maintenance_level": 0.25,
            },
        ),
        (
            "nozzle_plate",
            calculate_nozzle_plate_state,
            {
                "recoater_blade_state": {"health": 0.91},
                "heating_elements_state": {"health": 0.93},
                "cleaning_interface_state": {"health": 0.88},
                "thermal_firing_resistors_state": {"health": 0.89},
            },
            {
                "operational_load": 12,
                "contamination": 0.45,
                "humidity": 0.35,
                "temperature_stress": 0.28,
                "maintenance_level": 0.25,
            },
        ),
    ],
)
def test_seeded_uncertainty_changes_with_seed(
    component_name,
    calculator,
    kwargs,
    drivers,
):
    config_a = _seeded_config(1234)
    config_b = _seeded_config(5678)
    previous_state = {"health": 0.92}

    first = calculator(
        previous_state=copy.deepcopy(previous_state),
        drivers=copy.deepcopy(drivers),
        config=copy.deepcopy(config_a),
        **copy.deepcopy(kwargs),
    )
    second = calculator(
        previous_state=copy.deepcopy(previous_state),
        drivers=copy.deepcopy(drivers),
        config=copy.deepcopy(config_b),
        **copy.deepcopy(kwargs),
    )

    assert first["metrics"]["failure_risk_index"] != second["metrics"][
        "failure_risk_index"
    ] or first["metrics"]["maintenance_error_index"] != second["metrics"][
        "maintenance_error_index"
    ]


def test_low_maintenance_increases_uncertainty_for_recoater_blade():
    config = _seeded_config(1234)
    previous_state = {"health": 0.92}
    base_drivers = {
        "operational_load": 15,
        "contamination": 0.5,
        "humidity": 0.35,
    }

    low_maintenance = calculate_recoater_blade_state(
        previous_state=copy.deepcopy(previous_state),
        drivers={**base_drivers, "maintenance_level": 0.0},
        config=copy.deepcopy(config),
    )
    high_maintenance = calculate_recoater_blade_state(
        previous_state=copy.deepcopy(previous_state),
        drivers={**base_drivers, "maintenance_level": 1.0},
        config=copy.deepcopy(config),
    )

    assert low_maintenance["metrics"]["failure_risk_index"] > high_maintenance[
        "metrics"
    ]["failure_risk_index"]
    assert low_maintenance["metrics"]["maintenance_error_index"] > high_maintenance[
        "metrics"
    ]["maintenance_error_index"]
    assert low_maintenance["damage"]["total"] >= high_maintenance["damage"]["total"]
