from pathlib import Path

import pytest
import yaml

from model_mathematic.cleaning_interface import calculate_cleaning_interface_state
from model_mathematic.heating_elements import calculate_heating_elements_state
from model_mathematic.insulation_panels import calculate_insulation_panels_state
from model_mathematic.linear_guide import calculate_linear_guide_state
from model_mathematic.logic_engine import update_machine_state
from model_mathematic.nozzle_plate import calculate_nozzle_plate_state
from model_mathematic.recoater_drive_motor import calculate_recoater_drive_motor_state
from model_mathematic.temperature_sensors import calculate_temperature_sensors_state
from model_mathematic.thermal_firing_resistors import (
    calculate_thermal_firing_resistors_state,
)


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "model_parameters.yaml"


def load_real_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


BASE_DRIVERS = {
    "operational_load": 10,
    "contamination": 0.3,
    "humidity": 0.45,
    "temperature_stress": 0.25,
    "maintenance_level": 0.2,
}


OPTIONAL_COMPONENTS = {
    "linear_guide": (
        calculate_linear_guide_state,
        {},
    ),
    "recoater_drive_motor": (
        calculate_recoater_drive_motor_state,
        {"linear_guide_state": {"health": 1.0}},
    ),
    "thermal_firing_resistors": (
        calculate_thermal_firing_resistors_state,
        {"heating_elements_state": {"health": 1.0}},
    ),
    "cleaning_interface": (
        calculate_cleaning_interface_state,
        {},
    ),
    "temperature_sensors": (
        calculate_temperature_sensors_state,
        {},
    ),
    "insulation_panels": (
        calculate_insulation_panels_state,
        {},
    ),
}


NOMINAL_DRIVERS = {
    "linear_guide": {
        "operational_load": 1,
        "contamination": 0.0,
        "humidity": 0.0,
        "maintenance_level": 0.0,
    },
    "recoater_drive_motor": {
        "operational_load": 1,
        "contamination": 0.0,
        "humidity": 0.0,
        "temperature_stress": 0.0,
        "maintenance_level": 0.0,
    },
    "thermal_firing_resistors": {
        "operational_load": 1,
        "contamination": 0.0,
        "humidity": 0.0,
        "temperature_stress": 0.0,
        "maintenance_level": 0.0,
    },
    "cleaning_interface": {
        "operational_load": 1,
        "contamination": 0.0,
        "humidity": 0.0,
        "maintenance_level": 0.0,
    },
    "temperature_sensors": {
        "operational_load": 1,
        "temperature_stress": 0.0,
        "humidity": 0.0,
        "maintenance_level": 0.0,
    },
    "insulation_panels": {
        "operational_load": 1,
        "contamination": 0.0,
        "temperature_stress": 0.0,
        "humidity": 0.0,
        "maintenance_level": 0.0,
    },
}


@pytest.mark.parametrize("component_name", OPTIONAL_COMPONENTS)
def test_optional_component_output_structure_and_determinism(component_name):
    config = load_real_config()
    calculator, extra_kwargs = OPTIONAL_COMPONENTS[component_name]

    first = calculator(
        previous_state={"health": 1.0},
        drivers=BASE_DRIVERS,
        config=config,
        **extra_kwargs,
    )
    second = calculator(
        previous_state={"health": 1.0},
        drivers=BASE_DRIVERS,
        config=config,
        **extra_kwargs,
    )

    assert first == second
    assert set(first) == {
        "subsystem",
        "component",
        "health",
        "status",
        "damage",
        "metrics",
        "alerts",
    }
    assert first["component"] == component_name


@pytest.mark.parametrize("component_name", OPTIONAL_COMPONENTS)
def test_optional_components_degrade_with_load_and_maintenance_reduces_damage(
    component_name,
):
    config = load_real_config()
    calculator, extra_kwargs = OPTIONAL_COMPONENTS[component_name]

    no_load = calculator(
        previous_state={"health": 1.0},
        drivers={**BASE_DRIVERS, "operational_load": 0},
        config=config,
        **extra_kwargs,
    )
    low_maintenance = calculator(
        previous_state={"health": 1.0},
        drivers={**BASE_DRIVERS, "maintenance_level": 0.0},
        config=config,
        **extra_kwargs,
    )
    high_maintenance = calculator(
        previous_state={"health": 1.0},
        drivers={**BASE_DRIVERS, "maintenance_level": 1.0},
        config=config,
        **extra_kwargs,
    )

    assert no_load["damage"]["total"] == 0.0
    assert low_maintenance["health"] < 1.0
    assert high_maintenance["damage"]["total"] < low_maintenance["damage"]["total"]


@pytest.mark.parametrize("component_name", OPTIONAL_COMPONENTS)
def test_optional_nominal_lifetimes_reach_failure_threshold(component_name):
    config = load_real_config()
    calculator, extra_kwargs = OPTIONAL_COMPONENTS[component_name]
    target_cycles = config["components"][component_name]["calibration"][
        "target_cycles_until_failure"
    ]

    state = {"health": 1.0}

    for _ in range(target_cycles):
        state = calculator(
            previous_state=state,
            drivers=NOMINAL_DRIVERS[component_name],
            config=config,
            **extra_kwargs,
        )

    assert state["health"] == 0.1
    assert state["status"] == "FAILED"


@pytest.mark.parametrize("component_name", OPTIONAL_COMPONENTS)
def test_optional_damage_matches_reported_health_loss_for_small_loads(component_name):
    config = load_real_config()
    calculator, extra_kwargs = OPTIONAL_COMPONENTS[component_name]
    drivers = {**NOMINAL_DRIVERS[component_name], "operational_load": 0.0001}
    previous_state = {"health": 1.0}

    result = calculator(
        previous_state=previous_state,
        drivers=drivers,
        config=config,
        **extra_kwargs,
    )

    health_loss = round(previous_state["health"] - result["health"], 8)

    assert result["damage"]["total"] > 0.0
    assert result["damage"]["total"] == health_loss


def test_optional_damage_breakdowns_follow_relevant_drivers():
    config = load_real_config()

    low_linear = calculate_linear_guide_state(
        {"health": 1.0},
        {**BASE_DRIVERS, "contamination": 0.0},
        config,
    )
    high_linear = calculate_linear_guide_state(
        {"health": 1.0},
        {**BASE_DRIVERS, "contamination": 1.0},
        config,
    )
    assert (
        high_linear["damage"]["contamination_scoring"]
        > low_linear["damage"]["contamination_scoring"]
    )

    low_motor = calculate_recoater_drive_motor_state(
        {"health": 1.0},
        {**BASE_DRIVERS, "temperature_stress": 0.0},
        config,
        linear_guide_state={"health": 1.0},
    )
    high_motor = calculate_recoater_drive_motor_state(
        {"health": 1.0},
        {**BASE_DRIVERS, "temperature_stress": 1.0},
        config,
        linear_guide_state={"health": 1.0},
    )
    assert high_motor["damage"]["thermal_stress"] > low_motor["damage"]["thermal_stress"]

    low_cleaning = calculate_cleaning_interface_state(
        {"health": 1.0},
        {**BASE_DRIVERS, "contamination": 0.0},
        config,
    )
    high_cleaning = calculate_cleaning_interface_state(
        {"health": 1.0},
        {**BASE_DRIVERS, "contamination": 1.0},
        config,
    )
    assert (
        high_cleaning["damage"]["contamination_residue"]
        > low_cleaning["damage"]["contamination_residue"]
    )

    low_resistors = calculate_thermal_firing_resistors_state(
        {"health": 1.0},
        {**BASE_DRIVERS, "temperature_stress": 0.0},
        config,
        heating_elements_state={"health": 1.0},
    )
    high_resistors = calculate_thermal_firing_resistors_state(
        {"health": 1.0},
        {**BASE_DRIVERS, "temperature_stress": 1.0},
        config,
        heating_elements_state={"health": 1.0},
    )
    assert (
        high_resistors["damage"]["thermal_fatigue"]
        > low_resistors["damage"]["thermal_fatigue"]
    )

    low_sensors = calculate_temperature_sensors_state(
        {"health": 1.0},
        {**BASE_DRIVERS, "temperature_stress": 0.0},
        config,
    )
    high_sensors = calculate_temperature_sensors_state(
        {"health": 1.0},
        {**BASE_DRIVERS, "temperature_stress": 1.0},
        config,
    )
    assert high_sensors["damage"]["thermal_drift"] > low_sensors["damage"]["thermal_drift"]

    low_insulation = calculate_insulation_panels_state(
        {"health": 1.0},
        {**BASE_DRIVERS, "humidity": 0.0},
        config,
    )
    high_insulation = calculate_insulation_panels_state(
        {"health": 1.0},
        {**BASE_DRIVERS, "humidity": 1.0},
        config,
    )
    assert (
        high_insulation["damage"]["humidity_absorption"]
        > low_insulation["damage"]["humidity_absorption"]
    )


def test_optional_metrics_are_monotonic_with_degradation():
    config = load_real_config()

    linear_good = calculate_linear_guide_state({"health": 0.9}, NOMINAL_DRIVERS["linear_guide"], config)
    linear_bad = calculate_linear_guide_state({"health": 0.4}, NOMINAL_DRIVERS["linear_guide"], config)
    assert linear_bad["metrics"]["friction_coefficient"] > linear_good["metrics"]["friction_coefficient"]
    assert linear_bad["metrics"]["alignment_score"] < linear_good["metrics"]["alignment_score"]

    motor_good = calculate_recoater_drive_motor_state(
        {"health": 0.9},
        NOMINAL_DRIVERS["recoater_drive_motor"],
        config,
        linear_guide_state={"health": 1.0},
    )
    motor_bad = calculate_recoater_drive_motor_state(
        {"health": 0.4},
        NOMINAL_DRIVERS["recoater_drive_motor"],
        config,
        linear_guide_state={"health": 1.0},
    )
    assert motor_bad["metrics"]["torque_margin"] < motor_good["metrics"]["torque_margin"]
    assert motor_bad["metrics"]["current_draw_factor"] > motor_good["metrics"]["current_draw_factor"]

    cleaning_good = calculate_cleaning_interface_state({"health": 0.9}, NOMINAL_DRIVERS["cleaning_interface"], config)
    cleaning_bad = calculate_cleaning_interface_state({"health": 0.4}, NOMINAL_DRIVERS["cleaning_interface"], config)
    assert cleaning_bad["metrics"]["cleaning_efficiency"] < cleaning_good["metrics"]["cleaning_efficiency"]
    assert cleaning_bad["metrics"]["residue_buildup"] > cleaning_good["metrics"]["residue_buildup"]

    resistor_good = calculate_thermal_firing_resistors_state(
        {"health": 0.9},
        NOMINAL_DRIVERS["thermal_firing_resistors"],
        config,
        heating_elements_state={"health": 1.0},
    )
    resistor_bad = calculate_thermal_firing_resistors_state(
        {"health": 0.4},
        NOMINAL_DRIVERS["thermal_firing_resistors"],
        config,
        heating_elements_state={"health": 1.0},
    )
    assert resistor_bad["metrics"]["resistance_ohm"] > resistor_good["metrics"]["resistance_ohm"]
    assert resistor_bad["metrics"]["pulse_uniformity"] < resistor_good["metrics"]["pulse_uniformity"]

    sensors_good = calculate_temperature_sensors_state({"health": 0.9}, NOMINAL_DRIVERS["temperature_sensors"], config)
    sensors_bad = calculate_temperature_sensors_state({"health": 0.4}, NOMINAL_DRIVERS["temperature_sensors"], config)
    assert sensors_bad["metrics"]["drift_c"] > sensors_good["metrics"]["drift_c"]
    assert sensors_bad["metrics"]["calibration_confidence"] < sensors_good["metrics"]["calibration_confidence"]

    insulation_good = calculate_insulation_panels_state({"health": 0.9}, NOMINAL_DRIVERS["insulation_panels"], config)
    insulation_bad = calculate_insulation_panels_state({"health": 0.4}, NOMINAL_DRIVERS["insulation_panels"], config)
    assert insulation_bad["metrics"]["insulation_efficiency"] < insulation_good["metrics"]["insulation_efficiency"]
    assert insulation_bad["metrics"]["heat_loss_factor"] > insulation_good["metrics"]["heat_loss_factor"]


def test_logic_engine_handles_all_optional_components_and_partial_configs():
    config = load_real_config()

    full_result = update_machine_state(
        previous_state={},
        drivers=BASE_DRIVERS,
        config=config,
    )

    assert set(full_result["components"]) == set(config["components"])

    for component_name in OPTIONAL_COMPONENTS:
        partial_config = {
            "components": {
                component_name: config["components"][component_name],
            }
        }

        result = update_machine_state(
            previous_state={},
            drivers=BASE_DRIVERS,
            config=partial_config,
        )

        assert set(result["components"]) == {component_name}


def test_optional_cascades_increase_downstream_damage():
    config = load_real_config()

    healthy_motor = calculate_recoater_drive_motor_state(
        {"health": 1.0},
        BASE_DRIVERS,
        config,
        linear_guide_state={"health": 1.0},
    )
    guide_degraded_motor = calculate_recoater_drive_motor_state(
        {"health": 1.0},
        BASE_DRIVERS,
        config,
        linear_guide_state={"health": 0.25},
    )
    assert (
        guide_degraded_motor["metrics"]["guide_drag_factor"]
        > healthy_motor["metrics"]["guide_drag_factor"]
    )
    assert guide_degraded_motor["damage"]["total"] > healthy_motor["damage"]["total"]

    healthy_heating = calculate_heating_elements_state(
        {"health": 1.0},
        BASE_DRIVERS,
        config,
        temperature_sensors_state={"health": 1.0},
        insulation_panels_state={"health": 1.0},
    )
    degraded_controls_heating = calculate_heating_elements_state(
        {"health": 1.0},
        BASE_DRIVERS,
        config,
        temperature_sensors_state={"health": 0.25},
        insulation_panels_state={"health": 0.25},
    )
    assert (
        degraded_controls_heating["metrics"]["effective_load"]
        > healthy_heating["metrics"]["effective_load"]
    )
    assert degraded_controls_heating["damage"]["total"] > healthy_heating["damage"]["total"]

    healthy_resistors = calculate_thermal_firing_resistors_state(
        {"health": 1.0},
        BASE_DRIVERS,
        config,
        heating_elements_state={"health": 1.0},
    )
    degraded_heating_resistors = calculate_thermal_firing_resistors_state(
        {"health": 1.0},
        BASE_DRIVERS,
        config,
        heating_elements_state={"health": 0.25},
    )
    assert (
        degraded_heating_resistors["metrics"]["effective_temperature_stress"]
        > healthy_resistors["metrics"]["effective_temperature_stress"]
    )
    assert degraded_heating_resistors["damage"]["total"] > healthy_resistors["damage"]["total"]

    healthy_nozzle = calculate_nozzle_plate_state(
        {"health": 1.0},
        BASE_DRIVERS,
        config,
        recoater_blade_state={"health": 1.0},
        heating_elements_state={"health": 1.0},
        cleaning_interface_state={"health": 1.0},
        thermal_firing_resistors_state={"health": 1.0},
    )
    degraded_nozzle = calculate_nozzle_plate_state(
        {"health": 1.0},
        BASE_DRIVERS,
        config,
        recoater_blade_state={"health": 1.0},
        heating_elements_state={"health": 1.0},
        cleaning_interface_state={"health": 0.25},
        thermal_firing_resistors_state={"health": 0.25},
    )
    assert (
        degraded_nozzle["metrics"]["effective_contamination"]
        > healthy_nozzle["metrics"]["effective_contamination"]
    )
    assert (
        degraded_nozzle["metrics"]["effective_temperature_stress"]
        > healthy_nozzle["metrics"]["effective_temperature_stress"]
    )
    assert degraded_nozzle["damage"]["total"] > healthy_nozzle["damage"]["total"]
