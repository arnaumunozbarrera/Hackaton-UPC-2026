"""Adapter from internal Phase 1 output to the frontend/backend contract."""

from __future__ import annotations

from copy import deepcopy


DEPENDENCY_MAP = [
    {
        "source": "linear_guide",
        "target": "recoater_drive_motor",
        "impact": "medium",
        "description": "Guide friction increases drag demand on the recoater drive motor.",
    },
    {
        "source": "temperature_sensors",
        "target": "heating_elements",
        "impact": "medium",
        "description": "Sensor drift can reduce temperature control accuracy and increase heating load.",
    },
    {
        "source": "insulation_panels",
        "target": "heating_elements",
        "impact": "high",
        "description": "Insulation loss raises thermal demand on the heating elements.",
    },
    {
        "source": "heating_elements",
        "target": "thermal_firing_resistors",
        "impact": "medium",
        "description": "Thermal instability accelerates firing resistor fatigue.",
    },
    {
        "source": "recoater_blade",
        "target": "nozzle_plate",
        "impact": "high",
        "description": "Recoater blade wear increases effective contamination at the nozzle plate.",
    },
    {
        "source": "cleaning_interface",
        "target": "nozzle_plate",
        "impact": "medium",
        "description": "Reduced cleaning efficiency increases residue and nozzle clogging risk.",
    },
    {
        "source": "heating_elements",
        "target": "nozzle_plate",
        "impact": "medium",
        "description": "Heating element degradation increases effective thermal stress at the nozzle plate.",
    },
    {
        "source": "thermal_firing_resistors",
        "target": "nozzle_plate",
        "impact": "medium",
        "description": "Firing resistor degradation increases jetting instability at the nozzle plate.",
    },
]


def _normalize_component(component_id: str, component_state: dict) -> dict:
    """Convert a raw Phase 1 component state into the backend response contract.

    @param component_id: Component identifier from the Phase 1 output.
    @param component_state: Raw component state returned by the mathematical model.
    @return: Component state with stable response keys and numeric health.
    """
    component_state = deepcopy(component_state)
    damage = component_state.get("damage", {})
    metrics = component_state.get("metrics", {})
    return {
        "subsystem": component_state.get("subsystem"),
        "health": float(component_state.get("health", 1.0)),
        "status": component_state.get("status", "FUNCTIONAL"),
        "damage": damage,
        "metrics": metrics,
        "alerts": component_state.get("alerts", []),
    }


def adapt_phase1_output(phase1_output: dict) -> dict:
    """Adapt mathematical model output into the dashboard machine-state contract.

    @param phase1_output: Raw output from the Phase 1 logic engine.
    @return: Response payload containing aggregate machine state and normalized components.
    """
    raw_components = phase1_output.get("components", {})
    components = {
        component_id: _normalize_component(component_id, component_state)
        for component_id, component_state in raw_components.items()
    }

    health_values = [component["health"] for component in components.values()]
    overall_health = round(sum(health_values) / len(health_values), 4) if health_values else 1.0
    critical_components = [
        component_id
        for component_id, component in components.items()
        if component["status"] == "CRITICAL"
    ]
    failed_components = [
        component_id
        for component_id, component in components.items()
        if component["status"] == "FAILED"
    ]

    if failed_components:
        overall_status = "FAILED"
    elif any(component["status"] == "CRITICAL" for component in components.values()):
        overall_status = "CRITICAL"
    elif any(component["status"] == "DEGRADED" for component in components.values()):
        overall_status = "DEGRADED"
    else:
        overall_status = "FUNCTIONAL"

    return {
        "machine_state": {
            "overall_health": overall_health,
            "overall_status": overall_status,
            "critical_components": critical_components,
            "failed_components": failed_components,
        },
        "components": components,
    }


def get_dependencies_for_component(component_id: str) -> list[dict]:
    """Return human-readable dependency relationships touching a component.

    @param component_id: Component identifier selected by the user or simulation.
    @return: Dependency records where the component is either source or target.
    """
    return [
        dependency
        for dependency in DEPENDENCY_MAP
        if dependency["source"] == component_id or dependency["target"] == component_id
    ]
