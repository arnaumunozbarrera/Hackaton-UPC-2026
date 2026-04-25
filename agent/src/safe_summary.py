from typing import Any


def build_safe_summary(analysis: dict[str, Any]) -> str:
    if analysis["decision_count"] == 0:
        return "Overall summary: No immediate maintenance action is required based on the current analysis."

    lines = [
        f"Overall summary: run {analysis['scenario_name']} has overall priority {analysis['highest_priority']} and {analysis['decision_count']} maintenance recommendation(s).",
        "",
        "Recommendations:",
    ]

    for index, decision in enumerate(analysis["decisions"], start=1):
        forecast = decision["forecast_without_intervention"]
        selected = decision["selected_plan"]

        lines.extend(
            [
                "",
                f"{index}. {decision['component_id']}",
                f"- Issue: {decision['issue']}",
                f"- Priority: {decision['recommendation_priority']}",
                f"- Diagnosis: {decision['diagnosis_description']}",
                f"- Forecast without intervention: predicted_status={forecast['predicted_status']}, risk_score={forecast['risk_score']}, time_to_critical_steps={forecast['time_to_critical_steps']}, time_to_failure_steps={forecast['time_to_failure_steps']}",
                f"- Recommended action: {selected['actions_text']}",
                f"- Projected result: projected_status={selected['projected_status']}, projected_health_index={selected['projected_health_index']}, risk_score={selected['risk_score']}",
                f"- Expected effect: {selected['expected_effect']}",
                "- Evidence:",
            ]
        )

        for evidence in decision["evidence"]:
            lines.append(
                f"  - {evidence['timestamp']} | {evidence['component_id']} | {evidence['field']} = {evidence['value']}"
            )

    return "\n".join(lines)