from dataclasses import replace

from agent.src.diagnosis import diagnose_latest
from agent.src.forecast import forecast_from_health_trend
from agent.src.planner import recommend_action
from agent.src.schemas import AgentDecision, Forecast, Recommendation, Severity


def make_agent_decisions(run_id: str, latest_record: dict, history: list[dict], horizon_steps: int) -> list[AgentDecision]:
    """Create sorted maintenance decisions from diagnosis, forecast, and planning.

    @param run_id: Run identifier associated with the records.
    @param latest_record: Latest historian record used as current state.
    @param history: Historical records used for forecasting.
    @param horizon_steps: Forecast horizon used for recommendations.
    @return: Agent decisions ordered by priority and projected risk.
    """
    diagnoses = diagnose_latest(run_id, latest_record)
    decisions: list[AgentDecision] = []

    for diagnosis in diagnoses:
        forecast = forecast_from_health_trend(history, diagnosis.component_id, horizon_steps)
        recommendation = recommend_action(
            diagnosis=diagnosis,
            forecast=forecast,
            latest_record=latest_record,
            history=history,
            horizon_steps=horizon_steps,
        )
        recommendation = escalate_recommendation_priority(recommendation, forecast)

        if recommendation.priority == Severity.INFO:
            continue

        decisions.append(
            AgentDecision(
                diagnosis=diagnosis,
                forecast=forecast,
                recommendation=recommendation,
            )
        )

    return sorted(decisions, key=decision_sort_key)


def escalate_recommendation_priority(recommendation: Recommendation, forecast: Forecast) -> Recommendation:
    """Increase recommendation priority when the forecast enters critical horizons.

    @param recommendation: Initial recommendation generated from plan selection.
    @param forecast: Forecast without intervention.
    @return: Recommendation with priority escalated when risk timing justifies it.
    """
    if forecast.predicted_status in {"FAILED", "CRITICAL"}:
        return replace(recommendation, priority=Severity.CRITICAL)

    if forecast.time_to_failure_steps is not None and forecast.time_to_failure_steps <= forecast.horizon_steps:
        return replace(recommendation, priority=Severity.CRITICAL)

    if forecast.time_to_critical_steps is not None and forecast.time_to_critical_steps <= forecast.horizon_steps:
        if recommendation.priority == Severity.INFO:
            return replace(recommendation, priority=Severity.WARNING)

    return recommendation


def decision_sort_key(decision: AgentDecision) -> tuple[int, int, int, float]:
    """Build the sort key used to present the most urgent decisions first.

    @param decision: Agent decision to rank.
    @return: Tuple ordered by recommendation priority, status severity, timing, and risk.
    """
    severity_rank = {
        Severity.FAILED: 0,
        Severity.CRITICAL: 1,
        Severity.WARNING: 2,
        Severity.INFO: 3,
    }

    status_rank = {
        "FAILED": 0,
        "CRITICAL": 1,
        "DEGRADED": 2,
        "FUNCTIONAL": 3,
        "UNKNOWN": 4,
    }

    time_to_failure = decision.forecast.time_to_failure_steps
    if time_to_failure is None:
        time_to_failure = 10**9

    return (
        severity_rank[decision.recommendation.priority],
        status_rank.get(decision.forecast.predicted_status, 4),
        time_to_failure,
        -decision.forecast.risk_score,
    )
