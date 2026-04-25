from agent.src.schemas import ActionEvaluation, ActionType, Diagnosis


def evaluate_candidate_actions(
    diagnosis: Diagnosis,
    latest_record: dict,
    history: list[dict],
    horizon_steps: int,
) -> list[ActionEvaluation]:
    actions = candidate_actions_for_issue(diagnosis.issue)
    evaluations = []

    for action in actions:
        evaluations.append(
            evaluate_action(
                action=action,
                diagnosis=diagnosis,
                latest_record=latest_record,
                history=history,
                horizon_steps=horizon_steps,
            )
        )

    return sorted(evaluations, key=lambda evaluation: evaluation.risk_score)


def candidate_actions_for_issue(issue: str) -> list[ActionType]:
    if issue == "thermal_instability":
        return [
            ActionType.CONTINUE_OPERATION,
            ActionType.TRIGGER_COOLDOWN,
            ActionType.REDUCE_LOAD,
            ActionType.STOP_MACHINE,
            ActionType.SCHEDULE_MAINTENANCE,
        ]

    if issue == "nozzle_clogging":
        return [
            ActionType.CONTINUE_OPERATION,
            ActionType.RUN_CLEANING_CYCLE,
            ActionType.REDUCE_LOAD,
            ActionType.SCHEDULE_MAINTENANCE,
            ActionType.STOP_MACHINE,
        ]

    if issue == "recoater_wear":
        return [
            ActionType.CONTINUE_OPERATION,
            ActionType.REDUCE_LOAD,
            ActionType.SCHEDULE_MAINTENANCE,
            ActionType.REPLACE_COMPONENT,
            ActionType.STOP_MACHINE,
        ]

    return [
        ActionType.CONTINUE_OPERATION,
        ActionType.SCHEDULE_MAINTENANCE,
        ActionType.STOP_MACHINE,
    ]


def evaluate_action(
    action: ActionType,
    diagnosis: Diagnosis,
    latest_record: dict,
    history: list[dict],
    horizon_steps: int,
) -> ActionEvaluation:
    component_id = diagnosis.component_id
    current_health = latest_record["components"][component_id]["health_index"]
    degradation_rate = estimate_degradation_rate(history, component_id)

    multiplier = degradation_multiplier(action, diagnosis.issue)
    recovery = immediate_recovery(action, diagnosis.issue)
    cost = action_cost(action)

    projected_health = current_health + recovery - degradation_rate * multiplier * horizon_steps
    projected_health = min(1.0, max(0.0, projected_health))

    predicted_status = status_from_health(projected_health)
    risk_score = compute_risk_score(projected_health, predicted_status, cost)

    return ActionEvaluation(
        action=action,
        projected_health_index=round(projected_health, 4),
        predicted_status=predicted_status,
        risk_score=round(risk_score, 4),
        expected_effect=build_expected_effect(action, diagnosis.issue, predicted_status, projected_health),
    )


def estimate_degradation_rate(history: list[dict], component_id: str) -> float:
    if len(history) < 2:
        return 0.0

    first = history[0]["components"][component_id]["health_index"]
    last = history[-1]["components"][component_id]["health_index"]
    steps = len(history) - 1

    return max((first - last) / steps, 0.0)


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


def action_cost(action: ActionType) -> float:
    costs = {
        ActionType.CONTINUE_OPERATION: 0.0,
        ActionType.REDUCE_LOAD: 8.0,
        ActionType.TRIGGER_COOLDOWN: 10.0,
        ActionType.RUN_CLEANING_CYCLE: 12.0,
        ActionType.SCHEDULE_MAINTENANCE: 18.0,
        ActionType.REPLACE_COMPONENT: 35.0,
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


def compute_risk_score(projected_health: float, predicted_status: str, cost: float) -> float:
    status_penalty = {
        "FAILED": 200.0,
        "CRITICAL": 100.0,
        "DEGRADED": 30.0,
        "FUNCTIONAL": 0.0,
    }

    health_penalty = (1.0 - projected_health) * 100.0

    return status_penalty[predicted_status] + health_penalty + cost


def build_expected_effect(
    action: ActionType,
    issue: str,
    predicted_status: str,
    projected_health: float,
) -> str:
    if action == ActionType.CONTINUE_OPERATION:
        return f"No intervention applied. Projected status remains {predicted_status} with health index {projected_health:.3f}"

    if action == ActionType.TRIGGER_COOLDOWN:
        return f"Reduce thermal stress and slow heat-driven degradation. Projected status becomes {predicted_status} with health index {projected_health:.3f}"

    if action == ActionType.REDUCE_LOAD:
        return f"Lower operational stress and reduce degradation rate. Projected status becomes {predicted_status} with health index {projected_health:.3f}"

    if action == ActionType.RUN_CLEANING_CYCLE:
        return f"Reduce clogging and recover printhead efficiency. Projected status becomes {predicted_status} with health index {projected_health:.3f}"

    if action == ActionType.SCHEDULE_MAINTENANCE:
        return f"Partially recover component health and reduce degradation. Projected status becomes {predicted_status} with health index {projected_health:.3f}"

    if action == ActionType.REPLACE_COMPONENT:
        return f"Restore component condition at higher operational cost. Projected status becomes {predicted_status} with health index {projected_health:.3f}"

    if action == ActionType.STOP_MACHINE:
        return f"Minimize further degradation but with high downtime cost. Projected status becomes {predicted_status} with health index {projected_health:.3f}"

    return f"Apply action {action.value}. Projected status becomes {predicted_status} with health index {projected_health:.3f}"