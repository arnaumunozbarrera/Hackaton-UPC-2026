"""Hybrid heuristic teacher used only for offline AI training labels."""

from __future__ import annotations


HEURISTIC_TEACHER_TYPE = "heuristic_hybrid"
HEURISTIC_TEACHER_VERSION = "v1"


HEURISTIC_PROFILE_BY_COMPONENT = {
    "recoater_blade": {
        "risk_weight": 0.15,
        "persistence_weight": 0.08,
        "regime_weight": 0.09,
        "human_error_weight": 0.04,
        "preventive_weight": 0.16,
        "stability_weight": 0.02,
        "max_multiplier": 1.18,
        "min_multiplier": 0.78,
    },
    "recoater_drive_motor": {
        "risk_weight": 0.18,
        "persistence_weight": 0.11,
        "regime_weight": 0.10,
        "human_error_weight": 0.05,
        "preventive_weight": 0.18,
        "stability_weight": 0.02,
        "max_multiplier": 1.22,
        "min_multiplier": 0.8,
    },
    "nozzle_plate": {
        "risk_weight": 0.19,
        "persistence_weight": 0.09,
        "regime_weight": 0.12,
        "human_error_weight": 0.06,
        "preventive_weight": 0.17,
        "stability_weight": 0.02,
        "max_multiplier": 1.24,
        "min_multiplier": 0.82,
    },
}


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(float(value), maximum))


def _load_stress(operational_load: float) -> float:
    return _clamp((float(operational_load) - 0.5) / 1.5, 0.0, 1.0)


def _maintenance_gap(maintenance_level: float) -> float:
    return _clamp(1.0 - float(maintenance_level), 0.0, 1.0)


def _degradation(previous_health: float) -> float:
    return _clamp(1.0 - float(previous_health), 0.0, 1.0)


def _persistence_term(base_damage: float, previous_damage_per_usage: float) -> float:
    damage_reference = max(float(base_damage), 1e-6)
    return _clamp(float(previous_damage_per_usage) / damage_reference, 0.0, 1.4)


def _recoater_blade_risk(context: dict) -> float:
    contamination = float(context["contamination"])
    humidity = float(context["humidity"])
    maintenance_gap = _maintenance_gap(context["maintenance_level"])
    load_stress = _load_stress(context["operational_load"])
    degradation = _degradation(context["previous_health"])
    return _clamp(
        0.38 * contamination * (0.55 + 0.45 * humidity)
        + 0.28 * maintenance_gap * (0.4 + 0.6 * contamination)
        + 0.2 * load_stress
        + 0.14 * degradation,
        0.0,
        1.0,
    )


def _recoater_drive_motor_risk(context: dict) -> float:
    contamination = float(context["contamination"])
    humidity = float(context["humidity"])
    temperature_stress = float(context["temperature_stress"])
    maintenance_gap = _maintenance_gap(context["maintenance_level"])
    load_stress = _load_stress(context["operational_load"])
    guide_degradation = _degradation(context["linear_guide_health"])
    motor_degradation = _degradation(context["previous_health"])
    return _clamp(
        0.26 * contamination * (0.6 + 0.4 * humidity)
        + 0.24 * temperature_stress * (0.55 + 0.45 * load_stress)
        + 0.22 * guide_degradation
        + 0.18 * maintenance_gap
        + 0.10 * motor_degradation,
        0.0,
        1.0,
    )


def _nozzle_plate_risk(context: dict) -> float:
    contamination = float(context["contamination"])
    humidity = float(context["humidity"])
    temperature_stress = float(context["temperature_stress"])
    maintenance_gap = _maintenance_gap(context["maintenance_level"])
    load_stress = _load_stress(context["operational_load"])
    clogging = float(context["previous_clogging_ratio"])
    thermal_fatigue = float(context["previous_thermal_fatigue_index"])
    dependency_degradation = (
        _degradation(context["recoater_blade_health"])
        + _degradation(context["heating_elements_health"])
        + _degradation(context["cleaning_interface_health"])
        + _degradation(context["thermal_firing_resistors_health"])
    ) / 4.0
    return _clamp(
        0.22 * contamination * (0.5 + 0.5 * humidity)
        + 0.18 * temperature_stress
        + 0.18 * clogging
        + 0.14 * thermal_fatigue
        + 0.16 * dependency_degradation
        + 0.12 * maintenance_gap * (0.4 + 0.6 * load_stress),
        0.0,
        1.0,
    )


def _risk_interaction(component_id: str, context: dict) -> float:
    if component_id == "recoater_blade":
        return _recoater_blade_risk(context)
    if component_id == "recoater_drive_motor":
        return _recoater_drive_motor_risk(context)
    if component_id == "nozzle_plate":
        return _nozzle_plate_risk(context)
    raise KeyError(f"Unsupported heuristic teacher component: {component_id}")


def _regime_shift_term(component_id: str, context: dict, risk_interaction: float) -> float:
    maintenance_gap = _maintenance_gap(context["maintenance_level"])
    load_stress = _load_stress(context["operational_load"])
    degradation = _degradation(context["previous_health"])

    if component_id == "recoater_blade":
        threshold = 0.42
    elif component_id == "recoater_drive_motor":
        threshold = 0.45
    else:
        threshold = 0.48

    trigger = _clamp(risk_interaction - threshold, 0.0, 1.0)
    return _clamp(
        trigger * (0.45 + 0.35 * maintenance_gap + 0.2 * max(load_stress, degradation)),
        0.0,
        1.0,
    )


def _human_error_term(context: dict, risk_interaction: float) -> float:
    maintenance_level = _clamp(context["maintenance_level"], 0.0, 1.0)
    load_stress = _load_stress(context["operational_load"])
    degradation = _degradation(context["previous_health"])
    intervention_complexity = 0.35 + 0.35 * load_stress + 0.30 * degradation
    return _clamp(
        maintenance_level * risk_interaction * intervention_complexity,
        0.0,
        1.0,
    )


def _preventive_benefit_term(context: dict, risk_interaction: float) -> float:
    maintenance_level = _clamp(context["maintenance_level"], 0.0, 1.0)
    maintenance_gap = _maintenance_gap(context["maintenance_level"])
    load_stress = _load_stress(context["operational_load"])
    degradation = _degradation(context["previous_health"])
    benefit_exposure = (
        0.4
        + 0.3 * risk_interaction
        + 0.2 * load_stress
        + 0.1 * degradation
    )
    return _clamp(
        maintenance_level * benefit_exposure * (1.0 - 0.15 * maintenance_gap),
        0.0,
        1.0,
    )


def _stability_credit(context: dict, risk_interaction: float) -> float:
    maintenance_level = _clamp(context["maintenance_level"], 0.0, 1.0)
    previous_health = _clamp(context["previous_health"], 0.0, 1.0)
    return _clamp(maintenance_level * previous_health * (1.0 - risk_interaction), 0.0, 1.0)


def apply_hybrid_teacher(
    component_id: str,
    base_damage: float,
    context: dict,
) -> tuple[float, dict]:
    """Return a corrected training label derived from the mathematical baseline."""
    profile = HEURISTIC_PROFILE_BY_COMPONENT[component_id]
    base_damage = max(float(base_damage), 0.0)

    risk_interaction = _risk_interaction(component_id, context)
    persistence = _persistence_term(
        base_damage,
        context.get("previous_damage_per_usage", 0.0),
    )
    regime_shift = _regime_shift_term(component_id, context, risk_interaction)
    human_error = _human_error_term(context, risk_interaction)
    preventive_benefit = _preventive_benefit_term(context, risk_interaction)
    stability_credit = _stability_credit(context, risk_interaction)

    multiplier = (
        1.0
        + profile["risk_weight"] * risk_interaction
        + profile["persistence_weight"] * persistence
        + profile["regime_weight"] * regime_shift
        + profile["human_error_weight"] * human_error
        - profile["preventive_weight"] * preventive_benefit
        - profile["stability_weight"] * stability_credit
    )
    multiplier = _clamp(
        multiplier,
        profile["min_multiplier"],
        profile["max_multiplier"],
    )
    adjusted_damage = base_damage * multiplier

    return adjusted_damage, {
        "teacher_type": HEURISTIC_TEACHER_TYPE,
        "teacher_version": HEURISTIC_TEACHER_VERSION,
        "component_profile": component_id,
        "base_damage": round(base_damage, 8),
        "multiplier": round(multiplier, 8),
        "terms": {
            "risk_interaction": round(risk_interaction, 6),
            "persistence": round(persistence, 6),
            "regime_shift": round(regime_shift, 6),
            "human_error": round(human_error, 6),
            "preventive_benefit": round(preventive_benefit, 6),
            "stability_credit": round(stability_credit, 6),
        },
    }
