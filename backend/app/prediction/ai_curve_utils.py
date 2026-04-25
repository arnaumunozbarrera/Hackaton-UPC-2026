"""Shared helpers for AI prediction curves."""

from __future__ import annotations


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(float(value), maximum))


def calibrate_ai_health(
    predicted_health: float,
    previous_health: float,
) -> float:
    """Clamp the learned health prediction without adding visual variance."""
    return clamp(min(predicted_health, previous_health), 0.0, 1.0)
