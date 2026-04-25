"""FastAPI backend for the digital twin dashboard."""

from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import sys
from pathlib import Path

from app.adapters.phase1_adapter import adapt_phase1_output
from app.core.phase1 import get_default_simulation_config, load_phase1_config, run_phase1_update, to_phase1_drivers
from app.prediction.predictor import predict_component_failure
from app.schemas import AgentAskRequest, AgentLLMAnswerRequest , AgentLLMContextRequest, PredictionRequest, SimulationRunRequest, SimulationStepRequest
from app.simulation.simulation_runner import run_simulation, run_single_step
from app.storage import historian

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.src.llm_context import build_llm_context
from agent.src.llm_context import build_llm_messages
from agent.src.llm_service import generate_llm_answer
from agent.src.llm_service import generate_llm_answer_with_context
from agent.src.query import answer_question
from agent.src.service import analyze_scenario_response
from agent.src.sqlite_historian import SQLiteHistorian


app = FastAPI(title="Digital Twin Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

historian.initialize_database()
AGENT_HISTORIAN = SQLiteHistorian(Path(__file__).resolve().parents[1] / "storage" / "historian.sqlite")

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

@app.get("/api/agent/runs/{run_id}/analysis")
def get_agent_analysis(
    run_id: str,
    horizon_steps: int = 24,
    history_window_steps: int | None = None,
) -> dict:
    try:
        return analyze_scenario_response(
            historian=AGENT_HISTORIAN,
            scenario_name=run_id,
            horizon_steps=horizon_steps,
            history_window_steps=history_window_steps,
        )
    except ValueError as error:
        raise _structured_error(404, "agent_run_not_found", str(error)) from error
    except Exception as error:
        raise _structured_error(500, "agent_analysis_failed", str(error)) from error

@app.post("/api/agent/runs/{run_id}/ask")
def ask_agent(run_id: str, request: AgentAskRequest) -> dict:
    try:
        analysis = analyze_scenario_response(
            historian=AGENT_HISTORIAN,
            scenario_name=run_id,
            horizon_steps=request.horizon_steps,
            history_window_steps=request.history_window_steps,
        )
        answer = answer_question(analysis, request.question)

        response = {
            "run_id": run_id,
            "question": request.question,
            "answer": answer,
            "highest_priority": analysis["highest_priority"],
            "decision_count": analysis["decision_count"],
        }

        if request.include_analysis:
            response["analysis"] = analysis

        return response

    except ValueError as error:
        raise _structured_error(404, "agent_run_not_found", str(error)) from error
    except Exception as error:
        raise _structured_error(500, "agent_ask_failed", str(error)) from error

@app.post("/api/agent/runs/{run_id}/llm-context")
def get_agent_llm_context(run_id: str, request: AgentLLMContextRequest) -> dict:
    try:
        analysis = analyze_scenario_response(
            historian=AGENT_HISTORIAN,
            scenario_name=run_id,
            horizon_steps=request.horizon_steps,
            history_window_steps=request.history_window_steps,
        )

        context = build_llm_context(
            run_id=run_id,
            question=request.question,
            analysis=analysis,
            max_alternatives_per_decision=request.max_alternatives_per_decision,
        )

        return {
            "run_id": run_id,
            "question": request.question,
            "context": context,
            "messages": build_llm_messages(context),
        }

    except ValueError as error:
        raise _structured_error(404, "agent_run_not_found", str(error)) from error
    except Exception as error:
        raise _structured_error(500, "agent_llm_context_failed", str(error)) from error

@app.post("/api/agent/runs/{run_id}/llm-answer")
def get_agent_llm_answer(run_id: str, request: AgentLLMAnswerRequest) -> dict:
    try:
        analysis = analyze_scenario_response(
            historian=AGENT_HISTORIAN,
            scenario_name=run_id,
            horizon_steps=request.horizon_steps,
            history_window_steps=request.history_window_steps,
        )

        if request.include_context:
            return generate_llm_answer_with_context(
                run_id=run_id,
                question=request.question,
                analysis=analysis,
                max_alternatives_per_decision=request.max_alternatives_per_decision,
                provider=request.provider,
                model=request.model,
            )

        return generate_llm_answer(
            run_id=run_id,
            question=request.question,
            analysis=analysis,
            max_alternatives_per_decision=request.max_alternatives_per_decision,
            provider=request.provider,
            model=request.model,
        )

    except ValueError as error:
        raise _structured_error(404, "agent_run_not_found", str(error)) from error
    except RuntimeError as error:
        raise _structured_error(500, "agent_llm_runtime_error", str(error)) from error
    except Exception as error:
        raise _structured_error(500, "agent_llm_answer_failed", str(error)) from error

@app.get("/api/messages/{run_id}")
def get_messages(run_id: str) -> list[dict]:
    return historian.get_messages(run_id)


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
