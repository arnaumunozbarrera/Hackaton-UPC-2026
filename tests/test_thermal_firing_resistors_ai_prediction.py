import pytest

from app.prediction.thermal_firing_resistors_ai import (
    predict_thermal_firing_resistors_ai_from_timeline,
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
    temperature_stress: float,
    maintenance_level: float,
    heating_elements_health: float = 1.0,
) -> dict:
    degradation = 1.0 - health
    effective_temperature_stress = min(
        temperature_stress + 0.25 * (1.0 - heating_elements_health),
        1.0,
    )
    return {
        "usage_count": usage_count,
        "timestamp": f"2026-01-01T00:{int(usage_count):02d}:00Z",
        "drivers": {
            "operational_load": 0.9,
            "contamination": contamination,
            "humidity": humidity,
            "temperature_stress": temperature_stress,
            "maintenance_level": maintenance_level,
        },
        "components": {
            "thermal_firing_resistors": {
                "health_index": health,
                "status": "FUNCTIONAL",
                "metrics": {
                    "resistance_ohm": 12.0 * (1.0 + 0.45 * degradation),
                    "firing_energy_factor": 1.0 + 0.5 * degradation,
                    "pulse_uniformity": 1.0 - 0.65 * degradation,
                    "misfire_risk": 0.7
                    * degradation
                    * (1.0 + effective_temperature_stress),
                    "effective_temperature_stress": effective_temperature_stress,
                    "heating_elements_health": heating_elements_health,
                    "effective_load": 1.0,
                },
            }
        },
    }


def test_thermal_firing_resistors_ai_predictor_trains_model_and_returns_curve():
    result = run_simulation(
        {
            "run_id": "thermal_firing_resistors_ai_integration",
            "scenario_id": "ai_test",
            "total_usages": 800,
            "usage_step": 4,
            "initial_conditions": {
                "temperature_c": 50,
                "humidity": 0.55,
                "contamination": 0.55,
                "operational_load": 0.95,
                "maintenance_level": 0.25,
                "stochasticity": 0.0,
            },
            "selected_component": "thermal_firing_resistors",
            "seed": 1234,
        }
    )

    prediction = predict_thermal_firing_resistors_ai_from_timeline(
        "thermal_firing_resistors_ai_integration",
        historian.get_component_history(
            "thermal_firing_resistors_ai_integration",
            "thermal_firing_resistors",
        ),
    )

    assert prediction["component_id"] == "thermal_firing_resistors"
    assert (
        prediction["model_family"]
        == "thermal_firing_resistors_sklearn_gradient_boosting"
    )
    assert prediction["prediction_method"] == "supervised_synthetic_gradient_boosting"
    assert prediction["training"]["trained_from_scratch"] is True
    assert prediction["training"]["training_samples"] > 10000
    assert prediction["confidence"] > 0.5

    ai_curve = prediction["ai_prediction_curve"]
    math_curve = [
        {
            "usage_count": point["usage_count"],
            "health": point["model_output"]["components"][
                "thermal_firing_resistors"
            ]["health"],
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


def test_thermal_firing_resistors_ai_predicts_more_damage_for_thermal_and_deposit_stress():
    low_risk_timeline = [
        _timeline_point(
            0,
            0.95,
            contamination=0.1,
            humidity=0.1,
            temperature_stress=0.1,
            maintenance_level=0.8,
            heating_elements_health=1.0,
        ),
        _timeline_point(
            20,
            0.94,
            contamination=0.1,
            humidity=0.1,
            temperature_stress=0.1,
            maintenance_level=0.8,
            heating_elements_health=1.0,
        ),
    ]
    high_risk_timeline = [
        _timeline_point(
            0,
            0.95,
            contamination=0.9,
            humidity=0.8,
            temperature_stress=0.9,
            maintenance_level=0.0,
            heating_elements_health=0.45,
        ),
        _timeline_point(
            20,
            0.82,
            contamination=0.9,
            humidity=0.8,
            temperature_stress=0.9,
            maintenance_level=0.0,
            heating_elements_health=0.45,
        ),
    ]

    low_risk_prediction = predict_thermal_firing_resistors_ai_from_timeline(
        "resistors_low_risk",
        low_risk_timeline,
    )
    high_risk_prediction = predict_thermal_firing_resistors_ai_from_timeline(
        "resistors_high_risk",
        high_risk_timeline,
    )

    assert (
        high_risk_prediction["ai_prediction_curve"][-1]["health"]
        < low_risk_prediction["ai_prediction_curve"][-1]["health"]
    )
    assert high_risk_prediction["explanation"]["top_factors"][0]["name"] in {
        "effective_temperature_stress",
        "heating_elements_health",
        "contamination",
        "pulse_uniformity",
        "maintenance_level",
    }
