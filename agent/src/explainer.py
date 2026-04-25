from agent.src.schemas import AgentDecision


def explain_decision(decision: AgentDecision) -> str:
    diagnosis = decision.diagnosis
    forecast = decision.forecast
    recommendation = decision.recommendation

    lines = [
        f"{recommendation.priority.value}: {diagnosis.component_id} requires attention.",
        "",
        f"Diagnosis: {diagnosis.description}.",
        f"Recommended action: {recommendation.action.value}.",
        f"Expected effect: {recommendation.expected_effect}.",
        "",
        build_forecast_sentence(decision),
        "",
        "Evidence:",
    ]

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
            return f"Forecast: if current conditions continue, the component is expected to reach FAILED in {forecast.time_to_failure_steps} steps."
        return "Forecast: if current conditions continue, the component is expected to reach FAILED within the forecast horizon."

    if forecast.predicted_status == "CRITICAL":
        if forecast.time_to_critical_steps is not None:
            return f"Forecast: if current conditions continue, the component is expected to reach CRITICAL in {forecast.time_to_critical_steps} steps."
        return "Forecast: if current conditions continue, the component is expected to reach CRITICAL within the forecast horizon."

    return f"Forecast: predicted status after {forecast.horizon_steps} steps is {forecast.predicted_status}, with risk score {forecast.risk_score:.2f}."