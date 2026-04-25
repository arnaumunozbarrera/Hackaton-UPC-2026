"""Shared helpers for Phase 1 degradation models."""


HEALTH_PRECISION = 8
DAMAGE_PRECISION = 8
FAILURE_THRESHOLD_TOLERANCE = 1e-6


def clamp(value, min_value, max_value):
    """Clamp a numeric value between inclusive bounds."""
    return max(min_value, min(value, max_value))


def get_status_from_health(health, health_config):
    """Return the component status for a health value and threshold config."""
    if health <= health_config["failed_threshold"]:
        return "FAILED"
    if health <= health_config["critical_threshold"]:
        return "CRITICAL"
    if health <= health_config["degraded_threshold"]:
        return "DEGRADED"
    return "FUNCTIONAL"


def is_component_enabled(config: dict, component_name: str) -> bool:
    """Return whether a component exists in config and is enabled."""
    components_config = config.get("components", {})
    component_config = components_config.get(component_name)

    if component_config is None:
        return False

    return component_config.get("enabled", True)
