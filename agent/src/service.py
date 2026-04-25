from typing import Any

from agent.src.decision import make_agent_decisions
from agent.src.response import build_agent_response
from agent.src.schemas import AgentDecision


def analyze_scenario(
    historian: Any,
    scenario_name: str,
    horizon_steps: int,
    history_window_steps: int | None = None,
) -> list[AgentDecision]:
    history = historian.get_recent_history(scenario_name, history_window_steps)
    latest_record = historian.get_latest_record(scenario_name)
    run_id = latest_record["run_id"]

    return make_agent_decisions(
        run_id=run_id,
        latest_record=latest_record,
        history=history,
        horizon_steps=horizon_steps,
    )


def analyze_scenario_response(
    historian: Any,
    scenario_name: str,
    horizon_steps: int,
    history_window_steps: int | None = None,
) -> dict[str, Any]:
    decisions = analyze_scenario(
        historian=historian,
        scenario_name=scenario_name,
        horizon_steps=horizon_steps,
        history_window_steps=history_window_steps,
    )

    return build_agent_response(
        scenario_name=scenario_name,
        decisions=decisions,
    )