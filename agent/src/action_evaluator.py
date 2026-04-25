from functools import reduce
from operator import mul

from agent.src.schemas import ActionPlanEvaluation, ActionType, Diagnosis
from agent.src.risk import compute_risk_score

def evaluate_candidate_action_plans(
    diagnosis: Diagnosis,
    latest_record: dict,
    history: list[dict],
    horizon_steps: int,
) -> list[ActionPlanEvaluation]:
    plans = candidate_action_plans_for_issue(diagnosis.issue)
    evaluations = []

    for actions in plans:
        evaluations.append(
            evaluate_action_plan(
                actions=actions,
                diagnosis=diagnosis,
                latest_record=latest_record,
                history=history,
                horizon_steps=horizon_steps,
            )
        )

    return sorted(evaluations, key=lambda evaluation: evaluation.risk_score)


def candidate_action_plans_for_issue(issue: str) -> list[tuple[ActionType, ...]]:
    if issue == "thermal_instability":
        return [
            (ActionType.CONTINUE_OPERATION,),
            (ActionType.TRIGGER_COOLDOWN,),
            (ActionType.REDUCE_LOAD,),
            (ActionType.TRIGGER_COOLDOWN, ActionType.REDUCE_LOAD),
            (ActionType.TRIGGER_COOLDOWN, ActionType.REDUCE_LOAD, ActionType.SCHEDULE_MAINTENANCE),
            (ActionType.STOP_MACHINE,),
            (ActionType.STOP_MACHINE, ActionType.SCHEDULE_MAINTENANCE),
        ]

    if issue == "nozzle_clogging":
        return [
            (ActionType.CONTINUE_OPERATION,),
            (ActionType.RUN_CLEANING_CYCLE,),
            (ActionType.REDUCE_LOAD,),
            (ActionType.RUN_CLEANING_CYCLE, ActionType.REDUCE_LOAD),
            (ActionType.RUN_CLEANING_CYCLE, ActionType.SCHEDULE_MAINTENANCE),
            (ActionType.SCHEDULE_MAINTENANCE,),
            (ActionType.STOP_MACHINE,),
        ]

    if issue == "recoater_wear":
        return [
            (ActionType.CONTINUE_OPERATION,),
            (ActionType.REDUCE_LOAD,),
            (ActionType.SCHEDULE_MAINTENANCE,),
            (ActionType.REDUCE_LOAD, ActionType.SCHEDULE_MAINTENANCE),
            (ActionType.REPLACE_COMPONENT,),
            (ActionType.STOP_MACHINE,),
        ]

    return [
        (ActionType.CONTINUE_OPERATION,),
        (ActionType.SCHEDULE_MAINTENANCE,),
        (ActionType.STOP_MACHINE,),
    ]


def evaluate_action_plan(
    actions: tuple[ActionType, ...],
    diagnosis: Diagnosis,
    latest_record: dict,
    history: list[dict],
    horizon_steps: int,
) -> ActionPlanEvaluation:
    component_id = diagnosis.component_id
    current_health = latest_record["components"][component_id]["health_index"]
    degradation_rate = estimate_degradation_rate(history, component_id)

    multiplier = combined_degradation_multiplier(actions, diagnosis.issue)
    recovery = combined_immediate_recovery(actions, diagnosis.issue)
    cost = combined_action_cost(actions)

    projected_health = current_health + recovery - degradation_rate * multiplier * horizon_steps
    projected_health = min(1.0, max(0.0, projected_health))

    predicted_status = status_from_health(projected_health)
    risk_score = compute_risk_score(projected_health, predicted_status, cost)

    return ActionPlanEvaluation(
        actions=actions,
        projected_health_index=round(projected_health, 4),
        predicted_status=predicted_status,
        risk_score=round(risk_score, 4),
        expected_effect=build_expected_effect(actions, diagnosis.issue, predicted_status, projected_health),
    )


def estimate_degradation_rate(history: list[dict], component_id: str) -> float:
    if len(history) < 2:
        return 0.0

    first = history[0]["components"][component_id]["health_index"]
    last = history[-1]["components"][component_id]["health_index"]
    steps = len(history) - 1

    return max((first - last) / steps, 0.0)


def combined_degradation_multiplier(actions: tuple[ActionType, ...], issue: str) -> float:
    multipliers = [degradation_multiplier(action, issue) for action in actions]
    return reduce(mul, multipliers, 1.0)


def degradation_multiplier(action: ActionType, issue: str) -> float:
    if action == ActionType.CONTINUE_OPERATION:
        return 1.0

    if action == ActionType.STOP_MACHINE:
        return 0.05

    if action == ActionType.REDUCE_LOAD:
        return 0.55

    if action == ActionType.TRIGGER_COOLDOWN:
        if issue == "thermal_instability":
            return 0.35
        return 0.80

    if action == ActionType.RUN_CLEANING_CYCLE:
        if issue == "nozzle_clogging":
            return 0.45
        return 0.90

    if action == ActionType.SCHEDULE_MAINTENANCE:
        return 0.40

    if action == ActionType.REPLACE_COMPONENT:
        return 0.10

    if action == ActionType.IMPROVE_ENVIRONMENT:
        return 0.65

    return 1.0


def combined_immediate_recovery(actions: tuple[ActionType, ...], issue: str) -> float:
    return sum(immediate_recovery(action, issue) for action in actions)


def immediate_recovery(action: ActionType, issue: str) -> float:
    if action == ActionType.RUN_CLEANING_CYCLE and issue == "nozzle_clogging":
        return 0.12

    if action == ActionType.SCHEDULE_MAINTENANCE:
        return 0.18

    if action == ActionType.REPLACE_COMPONENT:
        return 0.65

    if action == ActionType.TRIGGER_COOLDOWN and issue == "thermal_instability":
        return 0.06

    return 0.0


def combined_action_cost(actions: tuple[ActionType, ...]) -> float:
    return sum(action_cost(action) for action in actions)


def action_cost(action: ActionType) -> float:
    costs = {
        ActionType.CONTINUE_OPERATION: 0.0,
        ActionType.REDUCE_LOAD: 8.0,
        ActionType.TRIGGER_COOLDOWN: 10.0,
        ActionType.RUN_CLEANING_CYCLE: 12.0,
        ActionType.SCHEDULE_MAINTENANCE: 18.0,
        ActionType.REPLACE_COMPONENT: 85.0,
        ActionType.IMPROVE_ENVIRONMENT: 14.0,
        ActionType.STOP_MACHINE: 45.0,
    }

    return costs[action]


def status_from_health(health: float) -> str:
    if health <= 0.05:
        return "FAILED"
    if health <= 0.30:
        return "CRITICAL"
    if health <= 0.70:
        return "DEGRADED"
    return "FUNCTIONAL"

def build_expected_effect(
    actions: tuple[ActionType, ...],
    issue: str,
    predicted_status: str,
    projected_health: float,
) -> str:
    action_names = format_actions(actions)

    if actions == (ActionType.CONTINUE_OPERATION,):
        return f"No intervention applied. Projected status remains {predicted_status} with health index {projected_health:.3f}"

    if ActionType.STOP_MACHINE in actions:
        return f"Apply {action_names}. This minimizes further degradation with downtime cost. Projected status becomes {predicted_status} with health index {projected_health:.3f}"

    if ActionType.REPLACE_COMPONENT in actions:
        return f"Apply {action_names}. This restores component condition at higher operational cost. Projected status becomes {predicted_status} with health index {projected_health:.3f}"

    if issue == "thermal_instability":
        return f"Apply {action_names}. This reduces thermal stress and slows heat-driven degradation. Projected status becomes {predicted_status} with health index {projected_health:.3f}"

    if issue == "nozzle_clogging":
        return f"Apply {action_names}. This reduces clogging and recovers printhead efficiency. Projected status becomes {predicted_status} with health index {projected_health:.3f}"

    if issue == "recoater_wear":
        return f"Apply {action_names}. This reduces wear propagation and downstream contamination risk. Projected status becomes {predicted_status} with health index {projected_health:.3f}"

    return f"Apply {action_names}. Projected status becomes {predicted_status} with health index {projected_health:.3f}"


def format_actions(actions: tuple[ActionType, ...]) -> str:
    return " + ".join(action.value for action in actions)