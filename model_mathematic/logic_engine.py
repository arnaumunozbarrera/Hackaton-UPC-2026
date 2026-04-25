"""Phase 1 Logic Engine entry point."""

from .common import is_component_enabled
from .recoater_blade import calculate_recoater_blade_state
from .heating_elements import calculate_heating_elements_state
from .nozzle_plate import calculate_nozzle_plate_state


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
    previous_state = previous_state or {}
    previous_components = previous_state.get("components", {})

    components = {}

    if is_component_enabled(config, "recoater_blade"):
        previous_recoater_blade = previous_components.get("recoater_blade", {})

        components["recoater_blade"] = calculate_recoater_blade_state(
            previous_recoater_blade,
            drivers,
            config,
        )

    if is_component_enabled(config, "heating_elements"):
        previous_heating_elements = previous_components.get("heating_elements", {})

        components["heating_elements"] = calculate_heating_elements_state(
            previous_heating_elements,
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
        )

    return {
        "components": components,
    }