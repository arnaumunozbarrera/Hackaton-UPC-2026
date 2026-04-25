from app.schemas import ChatQueryRequest, PredictionRequest, SimulationRunRequest, SimulationStepRequest
from app.simulation.simulation_runner import _normalize_previous_model_output


def test_simulation_run_request_accepts_camel_case_payloads():
    request = SimulationRunRequest.model_validate(
        {
            "runId": "unity-run",
            "scenarioId": "unity-scenario",
            "totalUsages": 12,
            "usageStep": 3,
            "initialConditions": {
                "temperatureC": 43,
                "humidity": 0.4,
                "contamination": 0.2,
                "operationalLoad": 0.7,
                "maintenanceLevel": 0.6,
                "stochasticity": 0.3,
            },
            "selectedComponent": "heating_elements",
        }
    )

    assert request.run_id == "unity-run"
    assert request.scenario_id == "unity-scenario"
    assert request.total_usages == 12
    assert request.usage_step == 3
    assert request.initial_conditions.temperature_c == 43
    assert request.initial_conditions.operational_load == 0.7
    assert request.initial_conditions.maintenance_level == 0.6
    assert request.selected_component == "heating_elements"


def test_simulation_step_request_accepts_legacy_unity_fields():
    request = SimulationStepRequest.model_validate(
        {
            "runId": "unity-run",
            "stepIndex": 2,
            "usageCount": 8,
            "previousModelOutput": {"components": {"heating_elements": {"health": 0.9}}},
            "drivers": {
                "temperatureC": 44,
                "operationalLoad": 0.8,
                "maintenanceLevel": 0.5,
                "humidity": 0.2,
                "contamination": 0.1,
            },
        }
    )

    assert request.run_id == "unity-run"
    assert request.step_index == 2
    assert request.usage_count == 8
    assert request.drivers["temperature_c"] == 44
    assert request.drivers["operational_load"] == 0.8
    assert request.drivers["maintenance_level"] == 0.5


def test_prediction_and_chat_requests_accept_legacy_field_names():
    prediction = PredictionRequest.model_validate(
        {"runId": "run-1", "componentId": "nozzle_plate"}
    )
    chat = ChatQueryRequest.model_validate(
        {"runId": "run-1", "componentId": "nozzle_plate", "question": "Current status?"}
    )

    assert prediction.run_id == "run-1"
    assert prediction.component_id == "nozzle_plate"
    assert chat.run_id == "run-1"
    assert chat.component_id == "nozzle_plate"


def test_normalize_previous_model_output_accepts_historian_or_ui_shapes():
    historian_point = {
        "components": {
            "heating_elements": {
                "health_index": 0.82,
                "status": "DEGRADED",
                "metrics": {"effective_load": 0.7},
            }
        }
    }
    ui_point = {
        "model_output": {
            "components": {
                "heating_elements": {
                    "health": 0.76,
                    "status": "DEGRADED",
                    "metrics": {"effective_load": 0.9},
                }
            }
        }
    }

    normalized_historian = _normalize_previous_model_output(historian_point)
    normalized_ui = _normalize_previous_model_output(ui_point)

    assert normalized_historian["components"]["heating_elements"]["health"] == 0.82
    assert normalized_ui["components"]["heating_elements"]["health"] == 0.76
