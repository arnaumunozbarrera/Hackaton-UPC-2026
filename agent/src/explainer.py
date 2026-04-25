from agent.src.schemas import ActionPlanEvaluation, ActionType, AgentDecision


def explain_decision(decision: AgentDecision) -> str:
    diagnosis = decision.diagnosis
    recommendation = decision.recommendation
    selected = find_selected_evaluation(decision)

    lines = [
        f"{recommendation.priority.value}: {diagnosis.component_id} requires attention.",
        "",
        f"Diagnosis: {diagnosis.description}.",
        f"Recommended action plan: {format_actions(recommendation.actions)}.",
        f"Why this plan: {build_selection_reason(decision, selected)}",
        f"Expected effect: {recommendation.expected_effect}.",
        "",
        build_forecast_sentence(decision),
        "",
        "Evaluated alternatives:",
    ]

    for alternative in recommendation.alternatives[:5]:
        lines.append(
            f"- {format_actions(alternative.actions)}: projected_status={alternative.predicted_status}, "
            f"projected_health={alternative.projected_health_index}, risk_score={alternative.risk_score}"
        )

    lines.extend(
        [
            "",
            "Evidence:",
        ]
    )

    for evidence in diagnosis.evidence:
        lines.append(
            f"- {evidence.timestamp} | {evidence.component_id} | {evidence.field} = {evidence.value}"
        )

    return "\n".join(lines)


def explain_decisions(decisions: list[AgentDecision]) -> str:
    if not decisions:
        return "INFO: No immediate issues detected. The machine can continue operating under current conditions."

    sections = []

    for index, decision in enumerate(decisions, start=1):
        sections.append(f"Recommendation {index}")
        sections.append(explain_decision(decision))

    return "\n\n".join(sections)


def build_forecast_sentence(decision: AgentDecision) -> str:
    forecast = decision.forecast

    if forecast.predicted_status == "UNKNOWN":
        return "Forecast: there is not enough historical data to estimate future degradation."

    if forecast.predicted_status == "FAILED":
        if forecast.time_to_failure_steps is not None:
            return f"Forecast without intervention: if current conditions continue, the component is expected to reach FAILED in {forecast.time_to_failure_steps} steps."
        return "Forecast without intervention: if current conditions continue, the component is expected to reach FAILED within the forecast horizon."

    if forecast.predicted_status == "CRITICAL":
        if forecast.time_to_critical_steps is not None:
            return f"Forecast without intervention: if current conditions continue, the component is expected to reach CRITICAL in {forecast.time_to_critical_steps} steps."
        return "Forecast without intervention: if current conditions continue, the component is expected to reach CRITICAL within the forecast horizon."

    return f"Forecast without intervention: predicted status after {forecast.horizon_steps} steps is {forecast.predicted_status}, with risk score {forecast.risk_score:.2f}."


def build_selection_reason(decision: AgentDecision, selected: ActionPlanEvaluation) -> str:
    forecast = decision.forecast
    best_raw = decision.recommendation.alternatives[0]

    if forecast.predicted_status == "FAILED" and selected.predicted_status != "FAILED":
        return (
            f"it prevents the forecasted failure and projects the component to {selected.predicted_status} "
            f"with health index {selected.projected_health_index}"
        )

    if forecast.predicted_status == "CRITICAL" and selected.predicted_status in {"FUNCTIONAL", "DEGRADED"}:
        return (
            f"it avoids the forecasted critical state and projects the component to {selected.predicted_status} "
            f"with health index {selected.projected_health_index}"
        )

    if selected.actions != best_raw.actions:
        return (
            f"it stays within the acceptable risk range while using a less invasive plan than "
            f"{format_actions(best_raw.actions)}"
        )

    return (
        f"it has the best projected risk among the evaluated plans, with risk score {selected.risk_score} "
        f"and projected status {selected.predicted_status}"
    )


def find_selected_evaluation(decision: AgentDecision) -> ActionPlanEvaluation:
    for evaluation in decision.recommendation.alternatives:
        if evaluation.actions == decision.recommendation.actions:
            return evaluation

    raise ValueError("Selected action plan was not found in alternatives")


def format_actions(actions: tuple[ActionType, ...]) -> str:
    return " + ".join(action.value for action in actions)