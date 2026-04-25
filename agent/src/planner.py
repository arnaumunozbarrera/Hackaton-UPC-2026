from agent.src.action_evaluator import evaluate_candidate_action_plans
from agent.src.schemas import ActionPlanEvaluation, ActionType, Diagnosis, Forecast, Recommendation, Severity


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

    best = select_best_plan(evaluations, forecast)

    return Recommendation(
        actions=best.actions,
        priority=initial_priority_from_forecast(forecast),
        expected_effect=best.expected_effect,
        evidence=diagnosis.evidence,
        alternatives=evaluations,
    )


def select_best_plan(evaluations: list[ActionPlanEvaluation], forecast: Forecast) -> ActionPlanEvaluation:
    if not evaluations:
        raise ValueError("No action plan evaluations available")

    best = evaluations[0]
    tolerance = risk_tolerance_from_forecast(forecast)

    eligible = [
        evaluation
        for evaluation in evaluations
        if evaluation.risk_score <= best.risk_score + tolerance
        and status_rank(evaluation.predicted_status) <= status_rank(best.predicted_status) + 1
    ]

    non_continue_eligible = [
        evaluation
        for evaluation in eligible
        if evaluation.actions != (ActionType.CONTINUE_OPERATION,)
    ]

    if non_continue_eligible:
        eligible = non_continue_eligible

    return sorted(
        eligible,
        key=lambda evaluation: (
            plan_burden(evaluation.actions),
            len(evaluation.actions),
            evaluation.risk_score,
        ),
    )[0]

def status_rank(status: str) -> int:
    ranks = {
        "FUNCTIONAL": 0,
        "DEGRADED": 1,
        "CRITICAL": 2,
        "FAILED": 3,
        "UNKNOWN": 4,
    }

    return ranks.get(status, 4)

def risk_tolerance_from_forecast(forecast: Forecast) -> float:
    if forecast.predicted_status == "FAILED":
        return 8.0

    if forecast.predicted_status == "CRITICAL":
        return 18.0

    if forecast.predicted_status == "DEGRADED":
        return 25.0

    return 10.0


def plan_burden(actions: tuple[ActionType, ...]) -> float:
    burdens = {
        ActionType.CONTINUE_OPERATION: 100.0,
        ActionType.REDUCE_LOAD: 3.0,
        ActionType.TRIGGER_COOLDOWN: 4.0,
        ActionType.RUN_CLEANING_CYCLE: 4.0,
        ActionType.IMPROVE_ENVIRONMENT: 5.0,
        ActionType.SCHEDULE_MAINTENANCE: 9.0,
        ActionType.STOP_MACHINE: 14.0,
        ActionType.REPLACE_COMPONENT: 18.0,
    }

    return sum(burdens[action] for action in actions)


def initial_priority_from_forecast(forecast: Forecast) -> Severity:
    if forecast.predicted_status in {"FAILED", "CRITICAL"}:
        return Severity.CRITICAL

    if forecast.predicted_status == "DEGRADED":
        return Severity.WARNING

    return Severity.INFO


def find_selected_evaluation(recommendation: Recommendation) -> ActionPlanEvaluation:
    for evaluation in recommendation.alternatives:
        if evaluation.actions == recommendation.actions:
            return evaluation

    raise ValueError("Selected action plan was not found in alternatives")