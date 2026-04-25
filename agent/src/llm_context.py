import json
from typing import Any


def build_llm_context(
    run_id: str,
    question: str,
    analysis: dict[str, Any],
    max_alternatives_per_decision: int = 3,
) -> dict[str, Any]:
    return {
        "role": "grounded_maintenance_copilot",
        "run_id": run_id,
        "user_question": question,
        "rules": [
            "Use only the provided analysis data.",
            "Do not invent causes, values, timestamps, actions, forecasts, downtime, production impact, or cost.",
            "Do not override the selected action plan.",
            "Explain every decision in the decisions list.",
            "If several decisions have the same priority, do not call one of them the highest priority issue.",
            "Use exact action names, component names, statuses, health values, risk scores, timestamps, and metric values.",
        ],
        "analysis_summary": {
            "scenario_name": analysis["scenario_name"],
            "decision_count": analysis["decision_count"],
            "highest_priority": analysis["highest_priority"],
            "required_components": [
                decision["component_id"]
                for decision in analysis["decisions"]
            ],
        },
        "decisions": [
            compact_decision(decision, max_alternatives_per_decision)
            for decision in analysis["decisions"]
        ],
    }


def compact_decision(decision: dict[str, Any], max_alternatives: int) -> dict[str, Any]:
    return {
        "component_id": decision["component_id"],
        "issue": decision["issue"],
        "priority": decision["recommendation_priority"],
        "diagnosis": decision["diagnosis_description"],
        "forecast_without_intervention": {
            "predicted_status": decision["forecast_without_intervention"]["predicted_status"],
            "risk_score": decision["forecast_without_intervention"]["risk_score"],
            "time_to_critical_steps": decision["forecast_without_intervention"]["time_to_critical_steps"],
            "time_to_failure_steps": decision["forecast_without_intervention"]["time_to_failure_steps"],
        },
        "selected_plan": {
            "actions_text": decision["selected_plan"]["actions_text"],
            "projected_status": decision["selected_plan"]["projected_status"],
            "projected_health_index": decision["selected_plan"]["projected_health_index"],
            "risk_score": decision["selected_plan"]["risk_score"],
            "expected_effect": decision["selected_plan"]["expected_effect"],
        },
        "top_alternatives": [
            {
                "actions_text": alternative["actions_text"],
                "projected_status": alternative["predicted_status"],
                "projected_health_index": alternative["projected_health_index"],
                "risk_score": alternative["risk_score"],
            }
            for alternative in decision["alternatives"][:max_alternatives]
        ],
        "evidence": decision["evidence"],
    }


def build_llm_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    system_message = (
        "You are a grounded predictive maintenance copilot. "
        "You must only explain the provided agent analysis. "
        "You must not invent information. "
        "You must explain every required component. "
        "Return plain text only. "
        "Your response must contain zero asterisk characters. "
        "Do not use Markdown, bold, italics, code blocks, headings, tables, or bullet markers."
    )

    user_message = build_strict_user_prompt(context)

    return [
        {
            "role": "system",
            "content": system_message,
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]


def build_strict_user_prompt(context: dict[str, Any]) -> str:
    required_components = context["analysis_summary"]["required_components"]

    sections = [
        "Answer the user question using only the data below.",
        "",
        f"User question: {context['user_question']}",
        f"Run ID: {context['run_id']}",
        f"Overall priority: {context['analysis_summary']['highest_priority']}",
        f"Number of decisions: {context['analysis_summary']['decision_count']}",
        f"Required components to cover: {', '.join(required_components)}",
        "",
        "Hard rules:",
        "Return plain text only.",
        "Your response must contain zero asterisk characters.",
        "Do not use Markdown, bold, italics, code blocks, headings, tables, or bullet markers.",
        "Explain every required component exactly once.",
        "Do not say there is a single highest priority issue unless only one decision exists.",
        "Do not invent downtime, cost, production impact, root causes, or maintenance frequency.",
        "Use exact action names from the selected plans.",
        "Use exact evidence values and timestamps.",
        "",
        "Required output format:",
        "Overall summary:",
        "- One short sentence.",
        "",
        "Recommendations:",
    ]

    for index, component_id in enumerate(required_components, start=1):
        sections.extend(
            [
                f"{index}. {component_id}",
                "- Issue:",
                "- Priority:",
                "- Forecast without intervention:",
                "- Recommended action:",
                "- Projected result:",
                "- Evidence:",
            ]
        )

    sections.extend(
        [
            "",
            "Analysis data:",
            json.dumps(context, indent=2),
        ]
    )

    return "\n".join(sections)


def serialize_llm_context(context: dict[str, Any]) -> str:
    return json.dumps(context, indent=2)
