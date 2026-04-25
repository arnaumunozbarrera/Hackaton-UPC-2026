import pytest

from app.prediction.temperature_sensors_ai import (
    predict_temperature_sensors_ai_from_timeline,
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
    humidity: float,
    temperature_stress: float,
    maintenance_level: float,
) -> dict:
    degradation = 1.0 - health
    return {
        "usage_count": usage_count,
        "timestamp": f"2026-01-01T00:{int(usage_count):02d}:00Z",
        "drivers": {
            "operational_load": 0.9,
            "contamination": 0.0,
            "humidity": humidity,
            "temperature_stress": temperature_stress,
            "maintenance_level": maintenance_level,
        },
        "components": {
            "temperature_sensors": {
                "health_index": health,
                "status": "FUNCTIONAL",
                "metrics": {
                    "drift_c": 8.0 * degradation * (1.0 + temperature_stress),
                    "response_time_ms": 120.0 + 450.0 * degradation,
                    "signal_noise_index": degradation * (1.0 + humidity),
                    "calibration_confidence": 1.0 - 0.75 * degradation,
                },
            }
        },
    }


def test_temperature_sensors_ai_predictor_trains_model_and_returns_curve():
    result = run_simulation(
        {
            "run_id": "temperature_sensors_ai_integration",
            "scenario_id": "ai_test",
            "total_usages": 720,
            "usage_step": 4,
            "initial_conditions": {
                "temperature_c": 52,
                "humidity": 0.65,
                "contamination": 0.2,
                "operational_load": 0.95,
                "maintenance_level": 0.25,
                "stochasticity": 0.0,
            },
            "selected_component": "temperature_sensors",
            "seed": 1234,
        }
    )

    prediction = predict_temperature_sensors_ai_from_timeline(
        "temperature_sensors_ai_integration",
        historian.get_component_history(
            "temperature_sensors_ai_integration",
            "temperature_sensors",
        ),
    )

    assert prediction["component_id"] == "temperature_sensors"
    assert prediction["model_family"] == "temperature_sensors_sklearn_gradient_boosting"
    assert prediction["prediction_method"] == "supervised_synthetic_gradient_boosting"
    assert prediction["training"]["trained_from_scratch"] is True
    assert prediction["training"]["training_samples"] > 10000
    assert prediction["confidence"] > 0.5

    ai_curve = prediction["ai_prediction_curve"]
    math_curve = [
        {
            "usage_count": point["usage_count"],
            "health": point["model_output"]["components"]["temperature_sensors"][
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


def test_temperature_sensors_ai_predicts_more_damage_for_heat_and_humidity():
    low_risk_timeline = [
        _timeline_point(
            0,
            0.95,
            humidity=0.1,
            temperature_stress=0.1,
            maintenance_level=0.8,
        ),
        _timeline_point(
            20,
            0.94,
            humidity=0.1,
            temperature_stress=0.1,
            maintenance_level=0.8,
        ),
    ]
    high_risk_timeline = [
        _timeline_point(
            0,
            0.95,
            humidity=0.9,
            temperature_stress=0.9,
            maintenance_level=0.0,
        ),
        _timeline_point(
            20,
            0.82,
            humidity=0.9,
            temperature_stress=0.9,
            maintenance_level=0.0,
        ),
    ]

    low_risk_prediction = predict_temperature_sensors_ai_from_timeline(
        "temperature_sensors_low_risk",
        low_risk_timeline,
    )
    high_risk_prediction = predict_temperature_sensors_ai_from_timeline(
        "temperature_sensors_high_risk",
        high_risk_timeline,
    )

    assert (
        high_risk_prediction["ai_prediction_curve"][-1]["health"]
        < low_risk_prediction["ai_prediction_curve"][-1]["health"]
    )
    assert high_risk_prediction["explanation"]["top_factors"][0]["name"] in {
        "temperature_stress",
        "humidity",
        "drift_c",
        "calibration_confidence",
        "maintenance_level",
    }
