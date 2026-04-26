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
    """Run diagnosis, forecasting, and planning for one stored scenario or run.

    @param historian: Historian implementation exposing recent-history and latest-record methods.
    @param scenario_name: Scenario or run identifier understood by the historian.
    @param horizon_steps: Forecast horizon used for recommendations.
    @param history_window_steps: Optional history window limit.
    @return: Agent decisions for components requiring attention.
    """
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
    """Run scenario analysis and serialize the result for API consumers.

    @param historian: Historian implementation exposing recent-history and latest-record methods.
    @param scenario_name: Scenario or run identifier understood by the historian.
    @param horizon_steps: Forecast horizon used for recommendations.
    @param history_window_steps: Optional history window limit.
    @return: Structured agent response dictionary.
    """
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
