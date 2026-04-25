"""Phase 1 Logic Engine entry point."""

from .cleaning_interface import calculate_cleaning_interface_state
from .common import (
    get_previous_components_for_engine,
    is_component_enabled,
    validate_phase1_config,
)
from .heating_elements import calculate_heating_elements_state
from .insulation_panels import calculate_insulation_panels_state
from .linear_guide import calculate_linear_guide_state
from .nozzle_plate import calculate_nozzle_plate_state
from .recoater_blade import calculate_recoater_blade_state
from .recoater_drive_motor import calculate_recoater_drive_motor_state
from .temperature_sensors import calculate_temperature_sensors_state
from .thermal_firing_resistors import calculate_thermal_firing_resistors_state


def update_machine_state(previous_state: dict, drivers: dict, config: dict) -> dict:
    """Update machine state for Phase 1 without temporal simulation or persistence.

    This function is the public entry point for Phase 2.

    Phase 2 should call:
        update_machine_state(previous_state, drivers, config)

    This function does not add:
        - timestamp
        - run_id
        - scenario_id
        - step
        - persistence
    """
    config = config or {}
    validate_phase1_config(config)

    previous_state = previous_state or {}
    previous_components = get_previous_components_for_engine(previous_state, config)

    components = {}

    if is_component_enabled(config, "linear_guide"):
        previous_linear_guide = previous_components.get("linear_guide", {})

        components["linear_guide"] = calculate_linear_guide_state(
            previous_linear_guide,
            drivers,
            config,
        )

    if is_component_enabled(config, "recoater_drive_motor"):
        previous_recoater_drive_motor = previous_components.get(
            "recoater_drive_motor",
            {},
        )

        components["recoater_drive_motor"] = calculate_recoater_drive_motor_state(
            previous_recoater_drive_motor,
            drivers,
            config,
            linear_guide_state=components.get("linear_guide"),
        )

    if is_component_enabled(config, "recoater_blade"):
        previous_recoater_blade = previous_components.get("recoater_blade", {})

        components["recoater_blade"] = calculate_recoater_blade_state(
            previous_recoater_blade,
            drivers,
            config,
        )

    if is_component_enabled(config, "temperature_sensors"):
        previous_temperature_sensors = previous_components.get(
            "temperature_sensors",
            {},
        )

        components["temperature_sensors"] = calculate_temperature_sensors_state(
            previous_temperature_sensors,
            drivers,
            config,
        )

    if is_component_enabled(config, "insulation_panels"):
        previous_insulation_panels = previous_components.get(
            "insulation_panels",
            {},
        )

        components["insulation_panels"] = calculate_insulation_panels_state(
            previous_insulation_panels,
            drivers,
            config,
        )

    if is_component_enabled(config, "heating_elements"):
        previous_heating_elements = previous_components.get("heating_elements", {})

        components["heating_elements"] = calculate_heating_elements_state(
            previous_heating_elements,
            drivers,
            config,
            temperature_sensors_state=components.get("temperature_sensors"),
            insulation_panels_state=components.get("insulation_panels"),
        )

    if is_component_enabled(config, "thermal_firing_resistors"):
        previous_thermal_firing_resistors = previous_components.get(
            "thermal_firing_resistors",
            {},
        )

        components[
            "thermal_firing_resistors"
        ] = calculate_thermal_firing_resistors_state(
            previous_thermal_firing_resistors,
            drivers,
            config,
            heating_elements_state=components.get("heating_elements"),
        )

    if is_component_enabled(config, "cleaning_interface"):
        previous_cleaning_interface = previous_components.get(
            "cleaning_interface",
            {},
        )

        components["cleaning_interface"] = calculate_cleaning_interface_state(
            previous_cleaning_interface,
            drivers,
            config,
        )

    if is_component_enabled(config, "nozzle_plate"):
        previous_nozzle_plate = previous_components.get("nozzle_plate", {})

        components["nozzle_plate"] = calculate_nozzle_plate_state(
            previous_nozzle_plate,
            drivers,
            config,
            recoater_blade_state=components.get("recoater_blade"),
            heating_elements_state=components.get("heating_elements"),
            cleaning_interface_state=components.get("cleaning_interface"),
            thermal_firing_resistors_state=components.get("thermal_firing_resistors"),
        )

    return {
        "components": components,
    }
