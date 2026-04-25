from typing import Any


def answer_question(response: dict[str, Any], question: str) -> str:
    normalized_question = question.lower().strip()

    if is_status_question(normalized_question):
        return answer_status(response)

    if is_why_question(normalized_question):
        return answer_why(response)

    if is_forecast_question(normalized_question):
        return answer_forecast(response)

    if is_alternatives_question(normalized_question):
        return answer_alternatives(response)

    if is_evidence_question(normalized_question):
        return answer_evidence(response)

    if is_recommendation_question(normalized_question):
        return answer_recommendations(response)

    return answer_default(response)


def is_status_question(question: str) -> bool:
    keywords = ["status", "state", "health", "how is", "current"]
    return any(keyword in question for keyword in keywords)


def is_why_question(question: str) -> bool:
    keywords = ["why", "reason", "justify", "justification"]
    return any(keyword in question for keyword in keywords)


def is_recommendation_question(question: str) -> bool:
    keywords = ["do", "recommend", "action", "should", "fix", "avoid", "prevent"]
    return any(keyword in question for keyword in keywords)


def is_forecast_question(question: str) -> bool:
    keywords = ["future", "forecast", "predict", "happen", "if we continue", "nothing", "continue like this"]
    return any(keyword in question for keyword in keywords)


def is_evidence_question(question: str) -> bool:
    keywords = ["evidence", "proof", "timestamp", "data"]
    return any(keyword in question for keyword in keywords)


def is_alternatives_question(question: str) -> bool:
    keywords = ["alternative", "alternatives", "other options", "compare", "instead"]
    return any(keyword in question for keyword in keywords)


def answer_status(response: dict[str, Any]) -> str:
    if response["decision_count"] == 0:
        return "INFO: No immediate issues detected. The machine can continue operating under current conditions."

    lines = [
        f"Overall priority: {response['highest_priority']}.",
        f"Detected issues: {response['decision_count']}.",
    ]

    for decision in response["decisions"]:
        lines.append(
            f"- {decision['component_id']}: {decision['issue']} "
            f"({decision['recommendation_priority']})"
        )

    return "\n".join(lines)


def answer_recommendations(response: dict[str, Any]) -> str:
    if response["decision_count"] == 0:
        return "INFO: No action required under current conditions."

    lines = ["Recommended action plan:"]

    for decision in response["decisions"]:
        selected = decision["selected_plan"]
        lines.append(
            f"- {decision['component_id']}: {selected['actions_text']} "
            f"-> projected_status={selected['projected_status']}, "
            f"projected_health={selected['projected_health_index']}, "
            f"risk_score={selected['risk_score']}"
        )

    return "\n".join(lines)


def answer_why(response: dict[str, Any]) -> str:
    if response["decision_count"] == 0:
        return "INFO: No issue was detected, so no intervention is currently recommended."

    lines = ["Recommendation rationale:"]

    for decision in response["decisions"]:
        selected = decision["selected_plan"]
        forecast = decision["forecast_without_intervention"]

        lines.append(
            f"- {decision['component_id']}: without intervention, predicted_status="
            f"{forecast['predicted_status']}, time_to_critical_steps="
            f"{forecast['time_to_critical_steps']}, time_to_failure_steps="
            f"{forecast['time_to_failure_steps']}. The selected plan "
            f"{selected['actions_text']} projects status={selected['projected_status']}, "
            f"health={selected['projected_health_index']}, risk_score={selected['risk_score']}."
        )

        lines.append("  Evidence:")

        for evidence in decision["evidence"]:
            lines.append(
                f"  - {evidence['timestamp']} | {evidence['component_id']} | "
                f"{evidence['field']} = {evidence['value']}"
            )

    return "\n".join(lines)


def answer_forecast(response: dict[str, Any]) -> str:
    if response["decision_count"] == 0:
        return "INFO: No failure or critical degradation is forecasted from the current synthetic scenario."

    lines = ["Forecast without intervention:"]

    for decision in response["decisions"]:
        forecast = decision["forecast_without_intervention"]
        lines.append(
            f"- {decision['component_id']}: predicted_status={forecast['predicted_status']}, "
            f"time_to_critical_steps={forecast['time_to_critical_steps']}, "
            f"time_to_failure_steps={forecast['time_to_failure_steps']}, "
            f"risk_score={forecast['risk_score']}"
        )

    return "\n".join(lines)


def answer_evidence(response: dict[str, Any]) -> str:
    if response["decision_count"] == 0:
        return "INFO: No issue evidence is available because no issue was detected."

    lines = ["Evidence:"]

    for decision in response["decisions"]:
        lines.append(f"- {decision['component_id']}:")

        for evidence in decision["evidence"]:
            lines.append(
                f"  - {evidence['timestamp']} | {evidence['component_id']} | "
                f"{evidence['field']} = {evidence['value']}"
            )

    return "\n".join(lines)


def answer_alternatives(response: dict[str, Any]) -> str:
    if response["decision_count"] == 0:
        return "INFO: No alternatives were evaluated because no intervention is required."

    lines = ["Evaluated alternatives:"]

    for decision in response["decisions"]:
        lines.append(f"- {decision['component_id']}:")

        for alternative in decision["alternatives"][:5]:
            lines.append(
                f"  - {alternative['actions_text']}: "
                f"projected_status={alternative['predicted_status']}, "
                f"projected_health={alternative['projected_health_index']}, "
                f"risk_score={alternative['risk_score']}"
            )

    return "\n".join(lines)


def answer_default(response: dict[str, Any]) -> str:
    return response["copilot_text"]