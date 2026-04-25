import pytest

from app.prediction.recoater_drive_motor_ai import (
    predict_recoater_drive_motor_ai_from_timeline,
)
from app.simulation.simulation_runner import run_simulation
from app.storage import historian


@pytest.fixture(autouse=True)
def isolated_historian(tmp_path, monkeypatch):
    monkeypatch.setattr(historian, "DB_PATH", tmp_path / "historian.sqlite")
    historian.initialize_database()


def test_recoater_drive_motor_ai_predictor_trains_sklearn_model_and_returns_curve():
    result = run_simulation(
        {
            "run_id": "motor_ai_integration",
            "scenario_id": "ai_test",
            "total_usages": 800,
            "usage_step": 4,
            "initial_conditions": {
                "temperature_c": 48,
                "humidity": 0.55,
                "contamination": 0.55,
                "operational_load": 0.9,
                "maintenance_level": 0.25,
                "stochasticity": 0.0,
            },
            "selected_component": "recoater_drive_motor",
            "seed": 1234,
        }
    )

    prediction = predict_recoater_drive_motor_ai_from_timeline(
        "motor_ai_integration",
        historian.get_component_history(
            "motor_ai_integration",
            "recoater_drive_motor",
        ),
    )

    assert prediction["component_id"] == "recoater_drive_motor"
    assert prediction["model_family"] == "recoater_drive_motor_sklearn_gradient_boosting"
    assert prediction["prediction_method"] == "supervised_synthetic_gradient_boosting"
    assert prediction["training"]["trained_from_scratch"] is True
    assert prediction["training"]["training_samples"] > 10000
    assert prediction["confidence"] > 0.5

    ai_curve = prediction["ai_prediction_curve"]
    math_curve = [
        {
            "usage_count": point["usage_count"],
            "health": point["model_output"]["components"]["recoater_drive_motor"]["health"],
        }
        for point in result["timeline"]
    ]

    assert [point["usage_count"] for point in ai_curve] == [
        point["usage_count"] for point in math_curve
    ]
    assert ai_curve[0]["health"] == pytest.approx(math_curve[0]["health"])
    assert all(0.0 <= point["health"] <= 1.0 for point in ai_curve)
    assert any(
        abs(ai_point["health"] - math_point["health"]) > 0.0001
        for ai_point, math_point in zip(ai_curve[1:], math_curve[1:])
    )
    assert prediction["explanation"]["target"] == "damage_per_usage"
