"""Seeded uncertainty configuration for AI synthetic telemetry."""

from __future__ import annotations

from copy import deepcopy


AI_UNCERTAINTY_BY_COMPONENT = {
    "recoater_blade": {
        "maintenance_error_rate": 0.12,
        "failure_risk_scale": 0.08,
    },
    "recoater_drive_motor": {
        "maintenance_error_rate": 0.10,
        "failure_risk_scale": 0.07,
    },
    "nozzle_plate": {
        "maintenance_error_rate": 0.14,
        "failure_risk_scale": 0.09,
    },
}


def with_ai_uncertainty(
    config: dict,
    component_id: str,
    seed: int,
) -> tuple[dict, dict]:
    """Return a config copy with deterministic uncertainty enabled for AI use."""
    uncertainty = AI_UNCERTAINTY_BY_COMPONENT.get(component_id, {})
    adjusted_config = deepcopy(config)
    adjusted_config["seed"] = int(seed)

    component_config = adjusted_config.get("components", {}).get(component_id)
    if component_config is not None and uncertainty:
        component_config["uncertainty"] = dict(uncertainty)

    return adjusted_config, dict(uncertainty)
