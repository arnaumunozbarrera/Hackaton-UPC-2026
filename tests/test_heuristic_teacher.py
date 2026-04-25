from app.prediction.heuristic_teacher import apply_hybrid_teacher


def test_hybrid_teacher_is_deterministic_for_same_inputs():
    context = {
        "previous_health": 0.82,
        "operational_load": 1.2,
        "contamination": 0.65,
        "humidity": 0.55,
        "maintenance_level": 0.25,
        "previous_damage_per_usage": 0.004,
    }

    first_damage, first_metadata = apply_hybrid_teacher(
        "recoater_blade",
        0.006,
        context,
    )
    second_damage, second_metadata = apply_hybrid_teacher(
        "recoater_blade",
        0.006,
        context,
    )

    assert first_damage == second_damage
    assert first_metadata == second_metadata


def test_hybrid_teacher_increases_damage_in_higher_risk_context():
    base_damage = 0.005
    low_risk_damage, _ = apply_hybrid_teacher(
        "recoater_drive_motor",
        base_damage,
        {
            "previous_health": 0.92,
            "operational_load": 0.6,
            "contamination": 0.1,
            "humidity": 0.1,
            "temperature_stress": 0.1,
            "maintenance_level": 0.9,
            "linear_guide_health": 0.95,
            "previous_damage_per_usage": 0.001,
        },
    )
    high_risk_damage, _ = apply_hybrid_teacher(
        "recoater_drive_motor",
        base_damage,
        {
            "previous_health": 0.62,
            "operational_load": 1.9,
            "contamination": 0.9,
            "humidity": 0.8,
            "temperature_stress": 0.85,
            "maintenance_level": 0.1,
            "linear_guide_health": 0.4,
            "previous_damage_per_usage": 0.006,
        },
    )

    assert high_risk_damage > low_risk_damage


def test_hybrid_teacher_keeps_damage_non_negative_and_bounded():
    damage, metadata = apply_hybrid_teacher(
        "nozzle_plate",
        0.004,
        {
            "previous_health": 0.98,
            "operational_load": 0.4,
            "contamination": 0.0,
            "humidity": 0.0,
            "temperature_stress": 0.0,
            "maintenance_level": 1.0,
            "previous_clogging_ratio": 0.0,
            "previous_thermal_fatigue_index": 0.0,
            "previous_damage_per_usage": 0.0,
            "recoater_blade_health": 1.0,
            "heating_elements_health": 1.0,
            "cleaning_interface_health": 1.0,
            "thermal_firing_resistors_health": 1.0,
        },
    )

    assert 0.0 <= damage <= 0.004 * 1.3
    assert metadata["teacher_type"] == "heuristic_hybrid"
