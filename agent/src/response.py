from typing import Any

from agent.src.explainer import explain_decisions
from agent.src.explainer import format_actions
from agent.src.planner import find_selected_evaluation
from agent.src.schemas import ActionPlanEvaluation, AgentDecision, Evidence


def build_agent_response(scenario_name: str, decisions: list[AgentDecision]) -> dict[str, Any]:
    """Serialize agent decisions into the public response contract.

    @param scenario_name: Scenario or run identifier represented by the analysis.
    @param decisions: Agent decisions produced by the planner.
    @return: Structured response with summary text, decisions, and priority.
    """
    return {
        "scenario_name": scenario_name,
        "decision_count": len(decisions),
        "highest_priority": get_highest_priority(decisions),
        "copilot_text": explain_decisions(decisions),
        "decisions": [
            decision_to_dict(decision)
            for decision in decisions
        ],
    }


def decision_to_dict(decision: AgentDecision) -> dict[str, Any]:
    """Convert one AgentDecision dataclass into API-safe primitive values.

    @param decision: Agent decision containing diagnosis, forecast, and recommendation.
    @return: Serialized decision dictionary.
    """
    selected = find_selected_evaluation(decision.recommendation)

    return {
        "component_id": decision.diagnosis.component_id,
        "issue": decision.diagnosis.issue,
        "diagnosis_severity": decision.diagnosis.severity.value,
        "recommendation_priority": decision.recommendation.priority.value,
        "diagnosis_description": decision.diagnosis.description,
        "forecast_without_intervention": {
            "horizon_steps": decision.forecast.horizon_steps,
            "predicted_status": decision.forecast.predicted_status,
            "time_to_critical_steps": decision.forecast.time_to_critical_steps,
            "time_to_failure_steps": decision.forecast.time_to_failure_steps,
            "risk_score": round_float(decision.forecast.risk_score),
        },
        "selected_plan": {
            "actions": [
                action.value
                for action in decision.recommendation.actions
            ],
            "actions_text": format_actions(decision.recommendation.actions),
            "expected_effect": decision.recommendation.expected_effect,
            "projected_status": selected.predicted_status,
            "projected_health_index": round_float(selected.projected_health_index),
            "risk_score": round_float(selected.risk_score),
        },
        "alternatives": [
            action_plan_evaluation_to_dict(alternative)
            for alternative in decision.recommendation.alternatives
        ],
        "evidence": [
            evidence_to_dict(evidence)
            for evidence in decision.diagnosis.evidence
        ],
    }


def action_plan_evaluation_to_dict(evaluation: ActionPlanEvaluation) -> dict[str, Any]:
    return {
        "actions": [
            action.value
            for action in evaluation.actions
        ],
        "actions_text": format_actions(evaluation.actions),
        "projected_health_index": round_float(evaluation.projected_health_index),
        "predicted_status": evaluation.predicted_status,
        "risk_score": round_float(evaluation.risk_score),
        "expected_effect": evaluation.expected_effect,
    }


def evidence_to_dict(evidence: Evidence) -> dict[str, Any]:
    return {
        "run_id": evidence.run_id,
        "timestamp": evidence.timestamp,
        "component_id": evidence.component_id,
        "field": evidence.field,
        "value": round_float(evidence.value),
    }


def get_highest_priority(decisions: list[AgentDecision]) -> str:
    """Resolve the highest recommendation priority across all decisions.

    @param decisions: Agent decisions produced for a scenario.
    @return: Highest priority value, or INFO when no decisions exist.
    """
    if not decisions:
        return "INFO"

    rank = {
        "FAILED": 0,
        "CRITICAL": 1,
        "WARNING": 2,
        "INFO": 3,
    }

    priorities = [
        decision.recommendation.priority.value
        for decision in decisions
    ]

    return sorted(priorities, key=lambda priority: rank[priority])[0]


def round_float(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)

    return value
