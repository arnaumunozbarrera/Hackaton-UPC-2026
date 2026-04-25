import json
from typing import Any


def build_llm_context(
    run_id: str,
    question: str,
    analysis: dict[str, Any],
    max_alternatives_per_decision: int = 5,
) -> dict[str, Any]:
    return {
        "role": "grounded_maintenance_copilot",
        "run_id": run_id,
        "user_question": question,
        "rules": [
            "Answer only using the provided analysis data.",
            "Do not invent causes, values, timestamps, actions, or forecasts.",
            "Every technical claim must be supported by evidence from the analysis.",
            "If the analysis is insufficient, say that the available data is insufficient.",
            "Do not override the selected action plan. You may explain it, not replace it.",
        ],
        "answer_requirements": {
            "include_priority": True,
            "include_recommended_actions": True,
            "include_forecast_without_intervention": True,
            "include_evidence": True,
            "include_uncertainty_when_needed": True,
        },
        "analysis_summary": {
            "scenario_name": analysis["scenario_name"],
            "decision_count": analysis["decision_count"],
            "highest_priority": analysis["highest_priority"],
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
        "diagnosis_severity": decision["diagnosis_severity"],
        "recommendation_priority": decision["recommendation_priority"],
        "diagnosis_description": decision["diagnosis_description"],
        "forecast_without_intervention": decision["forecast_without_intervention"],
        "selected_plan": decision["selected_plan"],
        "top_alternatives": decision["alternatives"][:max_alternatives],
        "evidence": decision["evidence"],
    }


def build_llm_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    system_message = (
        "You are a grounded predictive maintenance copilot for an industrial digital twin. "
        "Use only the provided context. Do not invent data. "
        "Explain the agent decision clearly and cite the evidence timestamps and metric values included in the context."
    )

    user_message = json.dumps(context, indent=2)

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


def serialize_llm_context(context: dict[str, Any]) -> str:
    return json.dumps(context, indent=2)