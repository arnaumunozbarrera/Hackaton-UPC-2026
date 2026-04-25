"""Adapter from internal Phase 1 output to the frontend/backend contract."""

from __future__ import annotations

from copy import deepcopy


DEPENDENCY_MAP = [
    {
        "source": "heating_elements",
        "target": "nozzle_plate",
        "impact": "medium",
        "description": "Thermal instability can accelerate nozzle clogging and reduce jetting efficiency.",
    },
    {
        "source": "recoater_blade",
        "target": "nozzle_plate",
        "impact": "high",
        "description": "Recoater blade wear can increase powder irregularity, which may increase nozzle contamination risk.",
    },
    {
        "source": "nozzle_plate",
        "target": "recoater_blade",
        "impact": "low",
        "description": "Reduced jetting uniformity can increase downstream powder handling corrections and inspection load.",
    },
    {
        "source": "heating_elements",
        "target": "recoater_blade",
        "impact": "low",
        "description": "Thermal instability can indirectly alter powder behavior and slightly worsen blade wear conditions.",
    },
    {
        "source": "nozzle_plate",
        "target": "heating_elements",
        "impact": "medium",
        "description": "Compensating for unstable jetting may increase thermal demand on the heating subsystem.",
    },
    {
        "source": "recoater_blade",
        "target": "heating_elements",
        "impact": "low",
        "description": "Recoater degradation can create process variability that increases heating adjustments.",
    },
]


ALLOWED_DAMAGE_KEYS = {
    "recoater_blade": ("total", "abrasive_wear", "contamination_damage"),
    "nozzle_plate": ("total", "clogging", "thermal_fatigue"),
    "heating_elements": ("total", "electrical_degradation", "thermal_overload"),
}

ALLOWED_METRIC_KEYS = {
    "recoater_blade": ("thickness_mm", "roughness_index", "wear_rate"),
    "nozzle_plate": ("clogging_ratio", "blocked_nozzles_pct", "jetting_efficiency"),
    "heating_elements": ("resistance_ohm", "energy_factor", "thermal_stability"),
}


def _filter_keys(payload: dict, allowed_keys: tuple[str, ...]) -> dict:
    return {key: payload[key] for key in allowed_keys if key in payload}


def _normalize_component(component_id: str, component_state: dict) -> dict:
    component_state = deepcopy(component_state)
    damage = component_state.get("damage", {})
    metrics = component_state.get("metrics", {})
    return {
        "subsystem": component_state.get("subsystem"),
        "health": float(component_state.get("health", 1.0)),
        "status": component_state.get("status", "FUNCTIONAL"),
        "damage": _filter_keys(damage, ALLOWED_DAMAGE_KEYS[component_id]),
        "metrics": _filter_keys(metrics, ALLOWED_METRIC_KEYS[component_id]),
        "alerts": component_state.get("alerts", []),
    }


def adapt_phase1_output(phase1_output: dict) -> dict:
    raw_components = phase1_output.get("components", {})
    components = {
        component_id: _normalize_component(component_id, component_state)
        for component_id, component_state in raw_components.items()
        if component_id in ALLOWED_DAMAGE_KEYS
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
    return [
        dependency
        for dependency in DEPENDENCY_MAP
        if dependency["source"] == component_id or dependency["target"] == component_id
    ]
