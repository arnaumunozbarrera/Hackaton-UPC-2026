"""Shared helpers for Phase 1 degradation models."""


HEALTH_PRECISION = 8
DAMAGE_PRECISION = 8
FAILURE_THRESHOLD_TOLERANCE = 1e-5

COMPONENT_MODEL_TYPES = {
    "recoater_blade": "linear_abrasive_wear",
    "linear_guide": "linear_friction_misalignment",
    "recoater_drive_motor": "weibull_motor_fatigue_ingress",
    "nozzle_plate": "clogging_thermal_fatigue",
    "thermal_firing_resistors": "exponential_resistor_fatigue",
    "cleaning_interface": "wiper_wear_residue",
    "heating_elements": "exponential_electrical_degradation",
    "temperature_sensors": "sensor_drift_response",
    "insulation_panels": "insulation_thermal_cycling",
}


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
    """Determine whether a component should be evaluated for the given config.

    @param config: Phase 1 configuration in wrapped or single-component form.
    @param component_name: Component identifier expected by the degradation engine.
    @return: True when the component is configured and not explicitly disabled.
    """
    config = config or {}
    components_config = config.get("components", {})

    if components_config:
        component_config = components_config.get(component_name)

        if component_config is None:
            return False

        return component_config.get("enabled", True)

    if infer_component_name_from_config(config) != component_name:
        return False

    return config.get("enabled", True)


def infer_component_name_from_config(config: dict) -> str | None:
    """Infer the component represented by a legacy single-component config.

    @param config: Component-level configuration without a top-level components map.
    @return: Matching component identifier, or None when the config cannot be inferred.
    """
    if not config or "components" in config:
        return None

    explicit_component = config.get("component")
    if explicit_component in COMPONENT_MODEL_TYPES:
        return explicit_component

    model_type = config.get("model_type")

    for component_name, expected_model_type in COMPONENT_MODEL_TYPES.items():
        if model_type == expected_model_type:
            return component_name

    return None


def get_previous_components_for_engine(
    previous_state: dict,
    config: dict,
) -> dict:
    """Normalize prior state so the logic engine can read component states uniformly.

    @param previous_state: Previous engine output in wrapped or component-only form.
    @param config: Configuration used to infer the component for legacy inputs.
    @return: Mapping of component identifiers to prior component states.
    """
    if not previous_state:
        return {}

    if "components" in previous_state:
        return previous_state.get("components", {})

    component_name = infer_component_name_from_config(config)

    if not component_name:
        return {}

    return {component_name: previous_state}


def iter_configured_components(config: dict):
    """Iterate component definitions from supported Phase 1 config shapes.

    @param config: Phase 1 configuration in wrapped or legacy single-component form.
    @return: Iterator yielding component name and component configuration pairs.
    """
    config = config or {}

    if "components" in config:
        yield from config.get("components", {}).items()
        return

    component_name = infer_component_name_from_config(config)

    if component_name:
        yield component_name, config


def validate_component_config(component_name: str, component_config: dict) -> None:
    """Validate the required Phase 1 configuration contract for one component.

    @param component_name: Component identifier being validated.
    @param component_config: Configuration section for the component.
    @raises ValueError: If required sections, thresholds, or calibration values are invalid.
    """
    required_sections = {
        "enabled",
        "subsystem",
        "model_type",
        "health",
        "calibration",
        "sensitivity",
        "alerts",
    }

    if component_name == "nozzle_plate":
        required_sections |= {"damage_weights", "metrics"}
    else:
        required_sections |= {"physical_properties"}

    missing_sections = required_sections - set(component_config)

    if missing_sections:
        missing = ", ".join(sorted(missing_sections))
        raise ValueError(f"{component_name} config is missing: {missing}")

    expected_model_type = COMPONENT_MODEL_TYPES.get(component_name)
    actual_model_type = component_config["model_type"]

    if expected_model_type and actual_model_type != expected_model_type:
        raise ValueError(
            f"{component_name} model_type must be {expected_model_type!r}, "
            f"got {actual_model_type!r}."
        )

    health = component_config["health"]
    calibration = component_config["calibration"]
    sensitivity = component_config["sensitivity"]

    required_health_keys = {
        "initial",
        "min",
        "max",
        "degraded_threshold",
        "critical_threshold",
        "failed_threshold",
    }
    missing_health_keys = required_health_keys - set(health)

    if missing_health_keys:
        missing = ", ".join(sorted(missing_health_keys))
        raise ValueError(f"{component_name} health config is missing: {missing}")

    required_calibration_keys = {
        "target_cycles_until_failure",
        "failure_threshold",
    }
    missing_calibration_keys = required_calibration_keys - set(calibration)

    if missing_calibration_keys:
        missing = ", ".join(sorted(missing_calibration_keys))
        raise ValueError(f"{component_name} calibration config is missing: {missing}")

    if "maintenance_protection" not in sensitivity:
        raise ValueError(
            f"{component_name} sensitivity config is missing: "
            "maintenance_protection"
        )

    if calibration["target_cycles_until_failure"] <= 0:
        raise ValueError(f"{component_name} target_cycles_until_failure must be > 0.")

    if not 0 <= calibration["failure_threshold"] < health["initial"] <= 1:
        raise ValueError(
            f"{component_name} requires 0 <= failure_threshold < initial <= 1."
        )

    if (
        health["failed_threshold"]
        >= health["critical_threshold"]
        or health["critical_threshold"]
        >= health["degraded_threshold"]
        or health["degraded_threshold"]
        >= health["initial"]
    ):
        raise ValueError(
            f"{component_name} health thresholds must satisfy "
            "failed < critical < degraded < initial."
        )

    if (
        abs(calibration["failure_threshold"] - health["failed_threshold"])
        > FAILURE_THRESHOLD_TOLERANCE
    ):
        raise ValueError(
            f"{component_name} calibration.failure_threshold must match "
            "health.failed_threshold."
        )

    if 1.0 - sensitivity["maintenance_protection"] < 0.0:
        raise ValueError(
            f"{component_name} maintenance_protection cannot make maintenance_factor "
            "negative at maintenance_level=1."
        )

    if component_name == "recoater_drive_motor":
        raw_weibull_shape = calibration.get("weibull_shape_beta")

        if raw_weibull_shape is None:
            raise ValueError(
                "recoater_drive_motor calibration config is missing: "
                "weibull_shape_beta"
            )

        weibull_shape = float(raw_weibull_shape)

        if weibull_shape <= 0:
            raise ValueError(
                "recoater_drive_motor weibull_shape_beta must be > 0."
            )

    if component_name == "nozzle_plate":
        weights = component_config["damage_weights"]
        required_weight_keys = {"clogging", "thermal_fatigue"}
        missing_weight_keys = required_weight_keys - set(weights)

        if missing_weight_keys:
            missing = ", ".join(sorted(missing_weight_keys))
            raise ValueError(f"nozzle_plate damage_weights is missing: {missing}")

        if abs(sum(weights.values()) - 1.0) > FAILURE_THRESHOLD_TOLERANCE:
            raise ValueError("nozzle_plate damage_weights must sum to 1.0.")

        metrics = component_config["metrics"]
        required_metric_keys = {
            "max_blocked_nozzles_pct",
            "min_jetting_efficiency",
            "jetting_efficiency_clogging_penalty",
        }
        missing_metric_keys = required_metric_keys - set(metrics)

        if missing_metric_keys:
            missing = ", ".join(sorted(missing_metric_keys))
            raise ValueError(
                f"nozzle_plate metrics config is missing: {missing}"
            )


def validate_phase1_config(config: dict) -> None:
    """Validate every component that appears in a Phase 1 configuration.

    @param config: Phase 1 configuration in wrapped or single-component form.
    @raises ValueError: If any configured component violates the expected contract.
    """
    for component_name, component_config in iter_configured_components(config):
        validate_component_config(component_name, component_config)


def get_component_config(config: dict, component_name: str) -> dict:
    """Return a component config from either root config or component-only config."""
    if "components" in config:
        return config["components"][component_name]
    return config


def get_previous_component_state(previous_state: dict, component_name: str) -> dict:
    """Return previous state for a component from wrapped or direct state input."""
    if not previous_state:
        return {}

    if "components" in previous_state:
        return previous_state.get("components", {}).get(component_name, {})

    return previous_state


def get_previous_health(
    previous_state: dict,
    component_name: str,
    health_config: dict,
) -> float:
    """Return previous component health with component initial as fallback."""
    component_state = get_previous_component_state(previous_state, component_name)
    return component_state.get("health", health_config["initial"])


def get_component_health(component_state: dict | None) -> float:
    """Return health for an optional dependency state, defaulting to healthy."""
    if not component_state:
        return 1.0

    return clamp(float(component_state.get("health", 1.0)), 0.0, 1.0)


def get_reported_damage(previous_health: float, rounded_health: float) -> float:
    """Calculate damage from rounded health values to preserve public consistency.

    @param previous_health: Health value before applying the current degradation step.
    @param rounded_health: Rounded health value returned by the model.
    @return: Non-negative damage value that reconciles with the visible health delta.
    """
    return max(
        0.0,
        round(previous_health - rounded_health, DAMAGE_PRECISION),
    )


def snap_health_to_failure_threshold(
    rounded_health: float,
    health_config: dict,
) -> float:
    """Snap near-threshold health to the configured failure threshold.

    @param rounded_health: Rounded health value after degradation.
    @param health_config: Health configuration containing the failed threshold.
    @return: Health value adjusted only when it is within calibration tolerance.
    """
    failed_threshold = health_config["failed_threshold"]

    if abs(rounded_health - failed_threshold) <= FAILURE_THRESHOLD_TOLERANCE:
        return round(failed_threshold, HEALTH_PRECISION)

    return rounded_health


def split_damage_by_pressure(total_damage: float, pressures: dict[str, float]) -> dict:
    """Allocate total damage across named degradation pressure contributors.

    @param total_damage: Damage value to distribute.
    @param pressures: Relative contribution weights by degradation source.
    @return: Per-source damage mapping rounded to model damage precision.
    """
    total_pressure = sum(pressures.values())

    if total_pressure <= 0:
        return {name: 0.0 for name in pressures}

    return {
        name: round(total_damage * pressure / total_pressure, DAMAGE_PRECISION)
        for name, pressure in pressures.items()
    }
