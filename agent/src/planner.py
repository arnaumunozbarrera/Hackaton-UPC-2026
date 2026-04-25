from agent.src.action_evaluator import evaluate_candidate_action_plans
from agent.src.schemas import Diagnosis, Forecast, Recommendation, Severity


def recommend_action(
    diagnosis: Diagnosis,
    forecast: Forecast,
    latest_record: dict,
    history: list[dict],
    horizon_steps: int,
) -> Recommendation:
    evaluations = evaluate_candidate_action_plans(
        diagnosis=diagnosis,
        latest_record=latest_record,
        history=history,
        horizon_steps=horizon_steps,
    )

    best = evaluations[0]

    return Recommendation(
        actions=best.actions,
        priority=initial_priority_from_forecast(forecast),
        expected_effect=best.expected_effect,
        evidence=diagnosis.evidence,
        alternatives=evaluations,
    )


def initial_priority_from_forecast(forecast: Forecast) -> Severity:
    if forecast.predicted_status in {"FAILED", "CRITICAL"}:
        return Severity.CRITICAL

    if forecast.predicted_status == "DEGRADED":
        return Severity.WARNING

    return Severity.INFO