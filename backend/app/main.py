"""FastAPI backend for the digital twin dashboard."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.chatbot import answer_chat_question
from app.adapters.phase1_adapter import adapt_phase1_output
from app.core.phase1 import get_default_simulation_config, load_phase1_config, run_phase1_update, to_phase1_drivers
from app.prediction.predictor import predict_component_failure
from app.schemas import ChatQueryRequest, PredictionRequest, SimulationRunRequest, SimulationStepRequest
from app.simulation.simulation_runner import run_simulation, run_single_step
from app.storage import historian


app = FastAPI(title="Digital Twin Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

historian.initialize_database()


def _structured_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/model/current")
def get_current_model_snapshot() -> dict:
    config = get_default_simulation_config()
    phase1_config = load_phase1_config()
    drivers = to_phase1_drivers(config["initial_conditions"])
    phase1_output = run_phase1_update(previous_state={}, drivers=drivers, config=phase1_config)
    return adapt_phase1_output(phase1_output)


@app.post("/api/simulation/run")
def run_full_simulation(request: SimulationRunRequest) -> dict:
    if request.usage_step > request.total_usages:
        raise _structured_error(400, "invalid_config", "usage_step must be lower than or equal to total_usages.")
    try:
        result = run_simulation(request.model_dump())
    except Exception as error:  # pragma: no cover
        raise _structured_error(500, "simulation_failed", str(error)) from error
    if not result["timeline"]:
        raise _structured_error(500, "empty_timeline", "Simulation returned no timeline points.")
    return result


@app.post("/api/simulation/step")
def run_simulation_step(request: SimulationStepRequest) -> dict:
    try:
        return run_single_step(request.model_dump())
    except Exception as error:  # pragma: no cover
        raise _structured_error(500, "step_failed", str(error)) from error


@app.post("/api/prediction/component")
def predict_failure(request: PredictionRequest) -> dict:
    try:
        return predict_component_failure(request.run_id, request.component_id)
    except Exception as error:  # pragma: no cover
        raise _structured_error(500, "prediction_failed", str(error)) from error


@app.get("/api/messages/{run_id}")
def get_messages(run_id: str) -> list[dict]:
    return historian.get_messages(run_id)


@app.post("/api/chat/query")
def chat_query(request: ChatQueryRequest) -> dict:
    try:
        return answer_chat_question(
            question=request.question,
            run_id=request.run_id,
            component_id=request.component_id,
        )
    except Exception as error:  # pragma: no cover
        raise _structured_error(500, "chat_query_failed", str(error)) from error


@app.get("/api/historian/runs/{run_id}/timeline")
def get_run_timeline(run_id: str) -> list[dict]:
    timeline = historian.get_run_timeline(run_id)
    if not timeline:
        raise _structured_error(404, "run_not_found", f"No timeline found for run_id={run_id}.")
    return timeline


@app.get("/api/historian/runs")
def get_runs() -> dict:
    runs = historian.list_runs()
    return {
        "runs": runs,
        "latest_run": historian.get_latest_run(),
    }


@app.delete("/api/historian")
def reset_historian() -> dict:
    historian.clear_database()
    return {"status": "cleared"}
