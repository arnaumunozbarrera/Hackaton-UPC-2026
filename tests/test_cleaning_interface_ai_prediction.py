import pytest

from app.prediction.cleaning_interface_ai import (
    predict_cleaning_interface_ai_from_timeline,
)
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
    degradation = 1.0 - health
    return {
        "usage_count": usage_count,
        "timestamp": f"2026-01-01T00:{int(usage_count):02d}:00Z",
        "drivers": {
            "operational_load": 0.9,
            "contamination": contamination,
            "humidity": humidity,
            "temperature_stress": 0.0,
            "maintenance_level": maintenance_level,
        },
        "components": {
            "cleaning_interface": {
                "health_index": health,
                "status": "FUNCTIONAL",
                "metrics": {
                    "cleaning_efficiency": 1.0 - 0.8 * degradation,
                    "residue_buildup": min(degradation + 0.15 * contamination, 1.0),
                    "wiper_wear_ratio": degradation,
                    "wipe_pressure_factor": 1.0 - 0.7 * degradation,
                },
            }
        },
    }


def test_cleaning_interface_ai_predictor_trains_model_and_returns_curve():
    result = run_simulation(
        {
            "run_id": "cleaning_interface_ai_integration",
            "scenario_id": "ai_test",
            "total_usages": 720,
            "usage_step": 4,
            "initial_conditions": {
                "temperature_c": 42,
                "humidity": 0.6,
                "contamination": 0.7,
                "operational_load": 0.95,
                "maintenance_level": 0.2,
                "stochasticity": 0.0,
            },
            "selected_component": "cleaning_interface",
            "seed": 1234,
        }
    )

    prediction = predict_cleaning_interface_ai_from_timeline(
        "cleaning_interface_ai_integration",
        historian.get_component_history(
            "cleaning_interface_ai_integration",
            "cleaning_interface",
        ),
    )

    assert prediction["component_id"] == "cleaning_interface"
    assert prediction["model_family"] == "cleaning_interface_sklearn_gradient_boosting"
    assert prediction["prediction_method"] == "supervised_synthetic_gradient_boosting"
    assert prediction["training"]["trained_from_scratch"] is True
    assert prediction["training"]["training_samples"] > 10000
    assert prediction["confidence"] > 0.5

    ai_curve = prediction["ai_prediction_curve"]
    math_curve = [
        {
            "usage_count": point["usage_count"],
            "health": point["model_output"]["components"]["cleaning_interface"][
                "health"
            ],
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


def test_cleaning_interface_ai_predicts_more_damage_for_dirty_humid_operation():
    low_risk_timeline = [
        _timeline_point(
            0,
            0.95,
            contamination=0.1,
            humidity=0.1,
            maintenance_level=0.8,
        ),
        _timeline_point(
            20,
            0.94,
            contamination=0.1,
            humidity=0.1,
            maintenance_level=0.8,
        ),
    ]
    high_risk_timeline = [
        _timeline_point(
            0,
            0.95,
            contamination=0.9,
            humidity=0.8,
            maintenance_level=0.0,
        ),
        _timeline_point(
            20,
            0.82,
            contamination=0.9,
            humidity=0.8,
            maintenance_level=0.0,
        ),
    ]

    low_risk_prediction = predict_cleaning_interface_ai_from_timeline(
        "cleaning_low_risk",
        low_risk_timeline,
    )
    high_risk_prediction = predict_cleaning_interface_ai_from_timeline(
        "cleaning_high_risk",
        high_risk_timeline,
    )

    assert (
        high_risk_prediction["ai_prediction_curve"][-1]["health"]
        < low_risk_prediction["ai_prediction_curve"][-1]["health"]
    )
    assert high_risk_prediction["explanation"]["top_factors"][0]["name"] in {
        "contamination",
        "residue_buildup",
        "humidity",
        "wipe_pressure_factor",
        "maintenance_level",
    }
