import pytest

import app.prediction.recoater_blade_ai as recoater_blade_ai
from app.prediction.artifact_store import artifact_exists
from app.prediction.recoater_blade_ai import predict_recoater_blade_ai_from_timeline
from app.simulation.simulation_runner import run_simulation
from app.storage import historian


@pytest.fixture(autouse=True)
def isolated_historian(tmp_path, monkeypatch):
    monkeypatch.setattr(historian, "DB_PATH", tmp_path / "historian.sqlite")
    historian.initialize_database()


def _timeline_point(
    usage_count: float,
    health: float,
    contamination: float,
    humidity: float,
    maintenance_level: float,
) -> dict:
    return {
        "usage_count": usage_count,
        "timestamp": f"2026-01-01T00:{int(usage_count):02d}:00Z",
        "drivers": {
            "operational_load": 0.8,
            "contamination": contamination,
            "humidity": humidity,
            "temperature_stress": 0.0,
            "maintenance_level": maintenance_level,
        },
        "components": {
            "recoater_blade": {
                "health_index": health,
                "status": "FUNCTIONAL",
                "metrics": {
                    "thickness_mm": 2.0 * health,
                    "roughness_index": 1.0 - health,
                    "wear_rate": max((0.95 - health) / max(usage_count, 1.0), 0.0),
                },
            }
        },
    }


def test_recoater_blade_ai_predictor_trains_sklearn_model_and_returns_curve():
    result = run_simulation(
        {
            "run_id": "recoater_ai_integration",
            "scenario_id": "ai_test",
            "total_usages": 600,
            "usage_step": 4,
            "initial_conditions": {
                "temperature_c": 42,
                "humidity": 0.55,
                "contamination": 0.7,
                "operational_load": 0.9,
                "maintenance_level": 0.25,
                "stochasticity": 0.0,
            },
            "selected_component": "recoater_blade",
            "seed": 1234,
        }
    )

    prediction = predict_recoater_blade_ai_from_timeline(
        "recoater_ai_integration",
        historian.get_component_history("recoater_ai_integration", "recoater_blade"),
    )

    assert prediction["component_id"] == "recoater_blade"
    assert prediction["model_family"] == "recoater_blade_sklearn_gradient_boosting"
    assert prediction["prediction_method"] == "supervised_synthetic_gradient_boosting"
    assert prediction["training"]["trained_from_scratch"] is True
    assert prediction["training"]["training_samples"] > 5000
    assert prediction["training"]["ai_uncertainty"]["enabled"] is True
    assert prediction["training"]["training_teacher"]["type"] == "heuristic_hybrid"
    assert prediction["confidence"] > 0.5
    ai_curve = prediction["ai_prediction_curve"]
    math_curve = [
        {
            "usage_count": point["usage_count"],
            "health": point["model_output"]["components"]["recoater_blade"]["health"],
        }
        for point in result["timeline"]
    ]
    assert [point["usage_count"] for point in ai_curve] == [
        point["usage_count"] for point in math_curve
    ]
    assert ai_curve[0]["health"] == pytest.approx(math_curve[0]["health"])
    assert any(
        abs(ai_point["health"] - math_point["health"]) > 0.0001
        for ai_point, math_point in zip(ai_curve[1:], math_curve[1:])
    )
    assert prediction["explanation"]["target"] == "damage_per_step"


def test_recoater_blade_ai_predicts_earlier_failure_for_higher_wear():
    low_wear_timeline = [
        _timeline_point(0, 0.95, contamination=0.1, humidity=0.1, maintenance_level=0.8),
        _timeline_point(20, 0.93, contamination=0.1, humidity=0.1, maintenance_level=0.8),
    ]
    high_wear_timeline = [
        _timeline_point(0, 0.95, contamination=0.9, humidity=0.8, maintenance_level=0.0),
        _timeline_point(20, 0.82, contamination=0.9, humidity=0.8, maintenance_level=0.0),
    ]

    low_wear_prediction = predict_recoater_blade_ai_from_timeline(
        "low_wear",
        low_wear_timeline,
    )
    high_wear_prediction = predict_recoater_blade_ai_from_timeline(
        "high_wear",
        high_wear_timeline,
    )

    assert (
        high_wear_prediction["ai_prediction_curve"][-1]["health"]
        < low_wear_prediction["ai_prediction_curve"][-1]["health"]
    )
    assert high_wear_prediction["explanation"]["top_factors"][0]["name"] in {
        "contamination",
        "humidity",
        "maintenance_level",
        "previous_health",
    }


def test_recoater_blade_ai_prediction_uses_persisted_artifact(monkeypatch):
    assert artifact_exists("recoater_blade") is True

    def fail_training():
        raise AssertionError("predictor should not train during inference")

    monkeypatch.setattr(recoater_blade_ai, "train_recoater_blade_model", fail_training)

    prediction = predict_recoater_blade_ai_from_timeline(
        "low_wear",
        [
            _timeline_point(
                0,
                0.95,
                contamination=0.1,
                humidity=0.1,
                maintenance_level=0.8,
            ),
            _timeline_point(
                20,
                0.93,
                contamination=0.1,
                humidity=0.1,
                maintenance_level=0.8,
            ),
        ],
    )

    assert prediction["component_id"] == "recoater_blade"
