import pytest

from app.prediction.heating_elements_ai import (
    predict_heating_elements_ai_from_timeline,
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
    temperature_sensors_health: float = 1.0,
    insulation_panels_health: float = 1.0,
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
            "heating_elements": {
                "health_index": health,
                "status": "FUNCTIONAL",
                "metrics": {
                    "resistance_ohm": 10.0 * (1.0 + 0.4 * degradation),
                    "energy_factor": 1.0 + 0.6 * degradation,
                    "thermal_stability": health * (1.0 - 0.3 * temperature_stress),
                    "temperature_control_error_c": (
                        12.0 * degradation * (1.0 + temperature_stress)
                    ),
                    "effective_temperature_stress": temperature_stress
                    + 0.25 * (1.0 - temperature_sensors_health),
                    "temperature_sensors_health": temperature_sensors_health,
                    "insulation_panels_health": insulation_panels_health,
                    "insulation_heat_loss_factor": 1.0
                    + 0.6 * (1.0 - insulation_panels_health),
                    "effective_load": 1.0,
                },
            }
        },
    }


def test_heating_elements_ai_predictor_trains_sklearn_model_and_returns_curve():
    result = run_simulation(
        {
            "run_id": "heating_elements_ai_integration",
            "scenario_id": "ai_test",
            "total_usages": 800,
            "usage_step": 4,
            "initial_conditions": {
                "temperature_c": 52,
                "humidity": 0.55,
                "contamination": 0.2,
                "operational_load": 0.95,
                "maintenance_level": 0.25,
                "stochasticity": 0.0,
            },
            "selected_component": "heating_elements",
            "seed": 1234,
        }
    )

    prediction = predict_heating_elements_ai_from_timeline(
        "heating_elements_ai_integration",
        historian.get_component_history(
            "heating_elements_ai_integration",
            "heating_elements",
        ),
    )

    assert prediction["component_id"] == "heating_elements"
    assert prediction["model_family"] == "heating_elements_sklearn_gradient_boosting"
    assert prediction["prediction_method"] == "supervised_synthetic_gradient_boosting"
    assert prediction["training"]["trained_from_scratch"] is True
    assert prediction["training"]["training_samples"] > 10000
    assert prediction["confidence"] > 0.5

    ai_curve = prediction["ai_prediction_curve"]
    math_curve = [
        {
            "usage_count": point["usage_count"],
            "health": point["model_output"]["components"]["heating_elements"][
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


def test_heating_elements_ai_predicts_more_damage_for_thermal_stress_and_heat_loss():
    low_risk_timeline = [
        _timeline_point(
            0,
            0.95,
            humidity=0.1,
            temperature_stress=0.1,
            maintenance_level=0.8,
            insulation_panels_health=1.0,
        ),
        _timeline_point(
            20,
            0.94,
            humidity=0.1,
            temperature_stress=0.1,
            maintenance_level=0.8,
            insulation_panels_health=1.0,
        ),
    ]
    high_risk_timeline = [
        _timeline_point(
            0,
            0.95,
            humidity=0.8,
            temperature_stress=0.9,
            maintenance_level=0.0,
            temperature_sensors_health=0.45,
            insulation_panels_health=0.45,
        ),
        _timeline_point(
            20,
            0.82,
            humidity=0.8,
            temperature_stress=0.9,
            maintenance_level=0.0,
            temperature_sensors_health=0.45,
            insulation_panels_health=0.45,
        ),
    ]

    low_risk_prediction = predict_heating_elements_ai_from_timeline(
        "heating_low_risk",
        low_risk_timeline,
    )
    high_risk_prediction = predict_heating_elements_ai_from_timeline(
        "heating_high_risk",
        high_risk_timeline,
    )

    assert (
        high_risk_prediction["ai_prediction_curve"][-1]["health"]
        < low_risk_prediction["ai_prediction_curve"][-1]["health"]
    )
    assert high_risk_prediction["explanation"]["top_factors"][0]["name"] in {
        "temperature_stress",
        "effective_temperature_stress",
        "insulation_heat_loss_factor",
        "thermal_stability",
        "maintenance_level",
    }
