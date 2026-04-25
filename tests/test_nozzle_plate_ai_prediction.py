import pytest

from app.prediction.nozzle_plate_ai import predict_nozzle_plate_ai_from_timeline
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
    clogging_ratio: float,
    thermal_fatigue_index: float,
) -> dict:
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
            "nozzle_plate": {
                "health_index": health,
                "status": "FUNCTIONAL",
                "metrics": {
                    "effective_contamination": contamination,
                    "effective_temperature_stress": temperature_stress,
                    "recoater_blade_health": 1.0,
                    "heating_elements_health": 1.0,
                    "cleaning_interface_health": 1.0,
                    "thermal_firing_resistors_health": 1.0,
                    "clogging_ratio": clogging_ratio,
                    "blocked_nozzles_pct": 100.0 * clogging_ratio,
                    "thermal_fatigue_index": thermal_fatigue_index,
                    "jetting_efficiency": health * (1.0 - 0.5 * clogging_ratio),
                },
            }
        },
    }


def test_nozzle_plate_ai_predictor_trains_sklearn_model_and_returns_curve():
    result = run_simulation(
        {
            "run_id": "nozzle_plate_ai_integration",
            "scenario_id": "ai_test",
            "total_usages": 720,
            "usage_step": 4,
            "initial_conditions": {
                "temperature_c": 50,
                "humidity": 0.62,
                "contamination": 0.72,
                "operational_load": 0.95,
                "maintenance_level": 0.2,
                "stochasticity": 0.0,
            },
            "selected_component": "nozzle_plate",
            "seed": 1234,
        }
    )

    prediction = predict_nozzle_plate_ai_from_timeline(
        "nozzle_plate_ai_integration",
        historian.get_component_history("nozzle_plate_ai_integration", "nozzle_plate"),
    )

    assert prediction["component_id"] == "nozzle_plate"
    assert prediction["model_family"] == "nozzle_plate_sklearn_gradient_boosting"
    assert prediction["prediction_method"] == "supervised_synthetic_gradient_boosting"
    assert prediction["training"]["trained_from_scratch"] is True
    assert prediction["training"]["training_samples"] > 10000
    assert prediction["training"]["ai_uncertainty"]["enabled"] is True
    assert prediction["training"]["training_teacher"]["type"] == "heuristic_hybrid"
    assert prediction["confidence"] > 0.5

    ai_curve = prediction["ai_prediction_curve"]
    math_curve = [
        {
            "usage_count": point["usage_count"],
            "health": point["model_output"]["components"]["nozzle_plate"]["health"],
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
    assert prediction["explanation"]["target"] == "damage_per_step"


def test_nozzle_plate_ai_predicts_more_damage_for_clogging_and_thermal_stress():
    low_risk_timeline = [
        _timeline_point(
            0,
            0.95,
            contamination=0.1,
            humidity=0.1,
            temperature_stress=0.1,
            maintenance_level=0.8,
            clogging_ratio=0.02,
            thermal_fatigue_index=0.01,
        ),
        _timeline_point(
            20,
            0.94,
            contamination=0.1,
            humidity=0.1,
            temperature_stress=0.1,
            maintenance_level=0.8,
            clogging_ratio=0.03,
            thermal_fatigue_index=0.02,
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
            clogging_ratio=0.2,
            thermal_fatigue_index=0.15,
        ),
        _timeline_point(
            20,
            0.82,
            contamination=0.9,
            humidity=0.8,
            temperature_stress=0.9,
            maintenance_level=0.0,
            clogging_ratio=0.34,
            thermal_fatigue_index=0.24,
        ),
    ]

    low_risk_prediction = predict_nozzle_plate_ai_from_timeline(
        "nozzle_low_risk",
        low_risk_timeline,
    )
    high_risk_prediction = predict_nozzle_plate_ai_from_timeline(
        "nozzle_high_risk",
        high_risk_timeline,
    )

    assert (
        high_risk_prediction["ai_prediction_curve"][-1]["health"]
        < low_risk_prediction["ai_prediction_curve"][-1]["health"]
    )
    assert high_risk_prediction["explanation"]["top_factors"][0]["name"] in {
        "effective_contamination",
        "effective_temperature_stress",
        "clogging_ratio",
        "jetting_efficiency",
        "maintenance_level",
    }
