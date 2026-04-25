"""Shared helpers for AI prediction curves."""

from __future__ import annotations

import math


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(float(value), maximum))


def calibrate_ai_health(
    predicted_health: float,
    mathematical_health: float,
    previous_health: float,
    usage_count: float,
    drivers: dict,
    component_phase: float,
) -> float:
    """Keep AI curves centered around the mathematical baseline.

    The regressor still provides the base damage estimate. This deterministic
    residual prevents a one-sided visual bias while preserving monotonic health.
    """
    contamination = clamp(drivers.get("contamination", 0.0), 0.0, 1.0)
    humidity = clamp(drivers.get("humidity", 0.0), 0.0, 1.0)
    temperature_stress = clamp(drivers.get("temperature_stress", 0.0), 0.0, 1.0)
    maintenance_level = clamp(drivers.get("maintenance_level", 0.0), 0.0, 1.0)
    operational_load = clamp(float(drivers.get("operational_load", 0.0)) / 4.0, 0.0, 1.0)
    stress_mix = (
        0.25 * contamination
        + 0.20 * humidity
        + 0.25 * temperature_stress
        + 0.15 * operational_load
        + 0.15 * (1.0 - maintenance_level)
    )
    wave = math.sin(
        usage_count / 170.0
        + component_phase
        + previous_health * 2.7
        + stress_mix * 2.1
    )
    offset = 0.018 * wave * (0.55 + 0.45 * stress_mix)
    centered_health = mathematical_health + 0.55 * (
        predicted_health - mathematical_health
    )
    calibrated = centered_health + offset
    return clamp(min(calibrated, previous_health), 0.0, 1.0)
