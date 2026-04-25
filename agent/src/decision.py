from agent.src.diagnosis import diagnose_latest
from agent.src.forecast import forecast_from_health_trend
from agent.src.planner import recommend_action
from agent.src.schemas import AgentDecision


def make_agent_decisions(run_id: str, latest_record: dict, history: list[dict], horizon_steps: int) -> list[AgentDecision]:
    diagnoses = diagnose_latest(run_id, latest_record)
    decisions: list[AgentDecision] = []

    for diagnosis in diagnoses:
        forecast = forecast_from_health_trend(history, diagnosis.component_id, horizon_steps)
        recommendation = recommend_action(diagnosis)
        decisions.append(
            AgentDecision(
                diagnosis=diagnosis,
                forecast=forecast,
                recommendation=recommendation,
            )
        )

    return decisions