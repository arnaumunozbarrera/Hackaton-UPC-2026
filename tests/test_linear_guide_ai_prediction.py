import pytest

from app.prediction.linear_guide_ai import predict_linear_guide_ai_from_timeline
from app.simulation.simulation_runner import run_simulation
from app.storage import historian


@pytest.fixture(autouse=True)
def isolated_historian(tmp_path, monkeypatch):
    monkeypatch.setattr(historian, "DB_PATH", tmp_path / "historian.sqlite")
    historian.initialize_database()


def _timeline_point(
    usage_count: float,
    health: float,
    operational_load: float,
    contamination: float,
    humidity: float,
    maintenance_level: float,
) -> dict:
    degradation = 1.0 - health
    return {
        "usage_count": usage_count,
        "timestamp": f"2026-01-01T00:{int(usage_count):02d}:00Z",
        "drivers": {
            "operational_load": operational_load,
            "contamination": contamination,
            "humidity": humidity,
            "temperature_stress": 0.0,
            "maintenance_level": maintenance_level,
        },
        "components": {
            "linear_guide": {
                "health_index": health,
                "status": "FUNCTIONAL",
                "metrics": {
                    "friction_coefficient": 0.05 + 0.25 * degradation,
                    "straightness_error_mm": 0.18 * degradation,
                    "carriage_drag_factor": 1.0 + 0.8 * degradation,
                    "alignment_score": health,
                },
            }
        },
    }


def test_linear_guide_ai_predictor_trains_sklearn_model_and_returns_curve():
    result = run_simulation(
        {
            "run_id": "linear_guide_ai_integration",
            "scenario_id": "ai_test",
            "total_usages": 900,
            "usage_step": 4,
            "initial_conditions": {
                "temperature_c": 42,
                "humidity": 0.6,
                "contamination": 0.65,
                "operational_load": 1.0,
                "maintenance_level": 0.2,
                "stochasticity": 0.0,
            },
            "selected_component": "linear_guide",
            "seed": 1234,
        }
    )

    prediction = predict_linear_guide_ai_from_timeline(
        "linear_guide_ai_integration",
        historian.get_component_history("linear_guide_ai_integration", "linear_guide"),
    )

    assert prediction["component_id"] == "linear_guide"
    assert prediction["model_family"] == "linear_guide_sklearn_gradient_boosting"
    assert prediction["prediction_method"] == "supervised_synthetic_gradient_boosting"
    assert prediction["training"]["trained_from_scratch"] is True
    assert prediction["training"]["training_samples"] > 5000
    assert prediction["confidence"] > 0.5

    ai_curve = prediction["ai_prediction_curve"]
    math_curve = [
        {
            "usage_count": point["usage_count"],
            "health": point["model_output"]["components"]["linear_guide"]["health"],
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


def test_linear_guide_ai_predicts_more_damage_for_dirty_high_load_rail():
    low_wear_timeline = [
        _timeline_point(
            0,
            0.95,
            operational_load=0.4,
            contamination=0.1,
            humidity=0.1,
            maintenance_level=0.8,
        ),
        _timeline_point(
            20,
            0.94,
            operational_load=0.4,
            contamination=0.1,
            humidity=0.1,
            maintenance_level=0.8,
        ),
    ]
    high_wear_timeline = [
        _timeline_point(
            0,
            0.95,
            operational_load=1.5,
            contamination=0.9,
            humidity=0.8,
            maintenance_level=0.0,
        ),
        _timeline_point(
            20,
            0.83,
            operational_load=1.5,
            contamination=0.9,
            humidity=0.8,
            maintenance_level=0.0,
        ),
    ]

    low_wear_prediction = predict_linear_guide_ai_from_timeline(
        "linear_low_wear",
        low_wear_timeline,
    )
    high_wear_prediction = predict_linear_guide_ai_from_timeline(
        "linear_high_wear",
        high_wear_timeline,
    )

    assert (
        high_wear_prediction["ai_prediction_curve"][-1]["health"]
        < low_wear_prediction["ai_prediction_curve"][-1]["health"]
    )
    assert high_wear_prediction["explanation"]["top_factors"][0]["name"] in {
        "operational_load",
        "contamination",
        "humidity",
        "carriage_drag_factor",
        "maintenance_level",
    }
