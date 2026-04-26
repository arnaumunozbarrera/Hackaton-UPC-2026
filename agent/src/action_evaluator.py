from functools import reduce
from operator import mul

from agent.src.health import status_from_health
from agent.src.risk import compute_risk_score
from agent.src.schemas import ActionPlanEvaluation, ActionType, Diagnosis


def evaluate_candidate_action_plans(
    diagnosis: Diagnosis,
    latest_record: dict,
    history: list[dict],
    horizon_steps: int,
) -> list[ActionPlanEvaluation]:
    """Evaluate all plausible action plans for a diagnosis.

    @param diagnosis: Diagnosis that identifies the component and issue.
    @param latest_record: Latest historian record used as the current state.
    @param history: Historical records used to estimate degradation rate.
    @param horizon_steps: Forecast horizon used for projected health.
    @return: Action plan evaluations ordered by ascending risk score.
    """
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
    """Select candidate action combinations that match an issue category.

    @param issue: Diagnosis issue identifier.
    @return: Ordered action tuples that should be evaluated for the issue.
    """
    if issue in {"thermal_instability", "firing_resistor_instability"}:
        return [
            (ActionType.CONTINUE_OPERATION,),
            (ActionType.TRIGGER_COOLDOWN,),
            (ActionType.REDUCE_LOAD,),
            (ActionType.TRIGGER_COOLDOWN, ActionType.REDUCE_LOAD),
            (
                ActionType.TRIGGER_COOLDOWN,
                ActionType.REDUCE_LOAD,
                ActionType.SCHEDULE_MAINTENANCE,
            ),
            (ActionType.SCHEDULE_MAINTENANCE,),
            (ActionType.REPLACE_COMPONENT,),
            (ActionType.STOP_MACHINE,),
            (ActionType.STOP_MACHINE, ActionType.SCHEDULE_MAINTENANCE),
        ]

    if issue in {"nozzle_clogging", "cleaning_interface_degradation"}:
        return [
            (ActionType.CONTINUE_OPERATION,),
            (ActionType.RUN_CLEANING_CYCLE,),
            (ActionType.REDUCE_LOAD,),
            (ActionType.RUN_CLEANING_CYCLE, ActionType.REDUCE_LOAD),
            (ActionType.RUN_CLEANING_CYCLE, ActionType.SCHEDULE_MAINTENANCE),
            (ActionType.SCHEDULE_MAINTENANCE,),
            (ActionType.REPLACE_COMPONENT,),
            (ActionType.STOP_MACHINE,),
        ]

    if issue in {
        "recoater_wear",
        "linear_guide_friction",
        "recoater_drive_motor_fatigue",
    }:
        return [
            (ActionType.CONTINUE_OPERATION,),
            (ActionType.REDUCE_LOAD,),
            (ActionType.SCHEDULE_MAINTENANCE,),
            (ActionType.REDUCE_LOAD, ActionType.SCHEDULE_MAINTENANCE),
            (ActionType.REPLACE_COMPONENT,),
            (ActionType.STOP_MACHINE,),
        ]

    if issue in {"sensor_drift", "insulation_loss"}:
        return [
            (ActionType.CONTINUE_OPERATION,),
            (ActionType.IMPROVE_ENVIRONMENT,),
            (ActionType.REDUCE_LOAD,),
            (ActionType.SCHEDULE_MAINTENANCE,),
            (ActionType.IMPROVE_ENVIRONMENT, ActionType.SCHEDULE_MAINTENANCE),
            (ActionType.REDUCE_LOAD, ActionType.SCHEDULE_MAINTENANCE),
            (ActionType.REPLACE_COMPONENT,),
            (ActionType.STOP_MACHINE,),
        ]

    return [
        (ActionType.CONTINUE_OPERATION,),
        (ActionType.REDUCE_LOAD,),
        (ActionType.SCHEDULE_MAINTENANCE,),
        (ActionType.REPLACE_COMPONENT,),
        (ActionType.STOP_MACHINE,),
    ]


def evaluate_action_plan(
    actions: tuple[ActionType, ...],
    diagnosis: Diagnosis,
    latest_record: dict,
    history: list[dict],
    horizon_steps: int,
) -> ActionPlanEvaluation:
    """Project component health and risk for one action plan.

    @param actions: Action tuple being evaluated.
    @param diagnosis: Diagnosis that identifies the component and issue.
    @param latest_record: Latest historian record used as the current state.
    @param history: Historical records used to estimate degradation rate.
    @param horizon_steps: Forecast horizon used for projected health.
    @return: ActionPlanEvaluation with projected status, risk, and expected effect.
    """
    component_id = diagnosis.component_id
    current_health = latest_record["components"][component_id]["health_index"]
    degradation_rate = estimate_degradation_rate(history, component_id)

    multiplier = combined_degradation_multiplier(actions, diagnosis.issue)
    recovery = combined_immediate_recovery(actions, diagnosis.issue)
    cost = combined_action_cost(actions)

    projected_health = (
        current_health
        + recovery
        - degradation_rate * multiplier * horizon_steps
    )
    projected_health = min(1.0, max(0.0, projected_health))

    predicted_status = status_from_health(projected_health)
    risk_score = compute_risk_score(projected_health, predicted_status, cost)

    return ActionPlanEvaluation(
        actions=actions,
        projected_health_index=round(projected_health, 4),
        predicted_status=predicted_status,
        risk_score=round(risk_score, 4),
        expected_effect=build_expected_effect(
            actions,
            diagnosis.issue,
            predicted_status,
            projected_health,
        ),
    )


def estimate_degradation_rate(history: list[dict], component_id: str) -> float:
    """Estimate per-step health loss from the available component history.

    @param history: Ordered historian records.
    @param component_id: Component identifier to inspect.
    @return: Non-negative average degradation rate per recorded step.
    """
    component_history = [
        record
        for record in history
        if component_id in record.get("components", {})
    ]

    if len(component_history) < 2:
        return 0.0

    first = component_history[0]["components"][component_id]["health_index"]
    last = component_history[-1]["components"][component_id]["health_index"]
    steps = len(component_history) - 1

    return max((first - last) / steps, 0.0)


def combined_degradation_multiplier(actions: tuple[ActionType, ...], issue: str) -> float:
    multipliers = [degradation_multiplier(action, issue) for action in actions]
    return reduce(mul, multipliers, 1.0)


def degradation_multiplier(action: ActionType, issue: str) -> float:
    """Return the expected degradation multiplier for one action and issue.

    @param action: Candidate action being scored.
    @param issue: Diagnosis issue identifier.
    @return: Multiplicative factor applied to projected degradation.
    """
    if action == ActionType.CONTINUE_OPERATION:
        return 1.0

    if action == ActionType.STOP_MACHINE:
        return 0.05

    if action == ActionType.REDUCE_LOAD:
        return 0.55

    if action == ActionType.TRIGGER_COOLDOWN:
        if issue in {"thermal_instability", "firing_resistor_instability"}:
            return 0.35
        return 0.80

    if action == ActionType.RUN_CLEANING_CYCLE:
        if issue in {"nozzle_clogging", "cleaning_interface_degradation"}:
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
    """Return the immediate health recovery expected from one action.

    @param action: Candidate action being scored.
    @param issue: Diagnosis issue identifier.
    @return: Additive projected health recovery.
    """
    if action == ActionType.RUN_CLEANING_CYCLE and issue in {
        "nozzle_clogging",
        "cleaning_interface_degradation",
    }:
        return 0.12

    if action == ActionType.SCHEDULE_MAINTENANCE:
        return 0.18

    if action == ActionType.REPLACE_COMPONENT:
        return 0.65

    if action == ActionType.TRIGGER_COOLDOWN and issue in {
        "thermal_instability",
        "firing_resistor_instability",
    }:
        return 0.06

    if action == ActionType.IMPROVE_ENVIRONMENT and issue in {
        "sensor_drift",
        "insulation_loss",
    }:
        return 0.08

    return 0.0


def combined_action_cost(actions: tuple[ActionType, ...]) -> float:
    return sum(action_cost(action) for action in actions)


def action_cost(action: ActionType) -> float:
    """Return the operational burden used as cost in risk scoring.

    @param action: Candidate action being scored.
    @return: Cost penalty used by the risk model.
    """
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


def build_expected_effect(
    actions: tuple[ActionType, ...],
    issue: str,
    predicted_status: str,
    projected_health: float,
) -> str:
    """Build a human-readable expected effect for an evaluated action plan.

    @param actions: Action tuple being evaluated.
    @param issue: Diagnosis issue identifier.
    @param predicted_status: Status projected after applying the actions.
    @param projected_health: Health index projected after applying the actions.
    @return: Explanation of the action plan effect.
    """
    action_names = format_actions(actions)

    if actions == (ActionType.CONTINUE_OPERATION,):
        return (
            "No intervention applied. "
            f"Projected status remains {predicted_status} "
            f"with health index {projected_health:.3f}"
        )

    if ActionType.STOP_MACHINE in actions:
        return (
            f"Apply {action_names}. "
            "This minimizes further degradation with downtime cost. "
            f"Projected status becomes {predicted_status} "
            f"with health index {projected_health:.3f}"
        )

    if ActionType.REPLACE_COMPONENT in actions:
        return (
            f"Apply {action_names}. "
            "This restores component condition at higher operational cost. "
            f"Projected status becomes {predicted_status} "
            f"with health index {projected_health:.3f}"
        )

    if issue == "thermal_instability":
        return (
            f"Apply {action_names}. "
            "This reduces thermal stress and slows heat-driven degradation. "
            f"Projected status becomes {predicted_status} "
            f"with health index {projected_health:.3f}"
        )

    if issue == "firing_resistor_instability":
        return (
            f"Apply {action_names}. "
            "This reduces heat-driven electrical fatigue and misfire risk. "
            f"Projected status becomes {predicted_status} "
            f"with health index {projected_health:.3f}"
        )

    if issue == "nozzle_clogging":
        return (
            f"Apply {action_names}. "
            "This reduces clogging and recovers printhead efficiency. "
            f"Projected status becomes {predicted_status} "
            f"with health index {projected_health:.3f}"
        )

    if issue == "cleaning_interface_degradation":
        return (
            f"Apply {action_names}. "
            "This improves cleaning effectiveness and slows residue-related degradation. "
            f"Projected status becomes {predicted_status} "
            f"with health index {projected_health:.3f}"
        )

    if issue == "recoater_wear":
        return (
            f"Apply {action_names}. "
            "This reduces wear propagation and downstream contamination risk. "
            f"Projected status becomes {predicted_status} "
            f"with health index {projected_health:.3f}"
        )

    if issue == "linear_guide_friction":
        return (
            f"Apply {action_names}. "
            "This reduces guide load, friction growth, and carriage drag risk. "
            f"Projected status becomes {predicted_status} "
            f"with health index {projected_health:.3f}"
        )

    if issue == "recoater_drive_motor_fatigue":
        return (
            f"Apply {action_names}. "
            "This reduces motor load, thermal stress, and fatigue accumulation. "
            f"Projected status becomes {predicted_status} "
            f"with health index {projected_health:.3f}"
        )

    if issue == "sensor_drift":
        return (
            f"Apply {action_names}. "
            "This reduces environmental stress and restores measurement confidence. "
            f"Projected status becomes {predicted_status} "
            f"with health index {projected_health:.3f}"
        )

    if issue == "insulation_loss":
        return (
            f"Apply {action_names}. "
            "This reduces thermal cycling stress and heat-loss propagation. "
            f"Projected status becomes {predicted_status} "
            f"with health index {projected_health:.3f}"
        )

    return (
        f"Apply {action_names}. "
        f"Projected status becomes {predicted_status} "
        f"with health index {projected_health:.3f}"
    )


def format_actions(actions: tuple[ActionType, ...]) -> str:
    return " + ".join(action.value for action in actions)
