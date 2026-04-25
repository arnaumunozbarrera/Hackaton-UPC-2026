import json
from pathlib import Path

from agent.src.decision import make_agent_decisions
from agent.src.explainer import explain_decisions
from agent.src.explainer import format_actions


def main() -> None:
    input_path = Path("data/synthetic_agent_history.json")

    with input_path.open("r", encoding="utf-8") as file:
        history = json.load(file)

    run_id = history[-1]["run_id"]
    latest_record = history[-1]
    horizon_steps = 24

    decisions = make_agent_decisions(
        run_id=run_id,
        latest_record=latest_record,
        history=history,
        horizon_steps=horizon_steps,
    )

    print("\nCopilot output")
    print("=" * 80)
    print(explain_decisions(decisions))

    print("\nTechnical debug")
    print("=" * 80)

    if not decisions:
        print("No issues detected.")
        return

    for index, decision in enumerate(decisions, start=1):
        print(f"\nDecision {index}")
        print(f"Issue: {decision.diagnosis.issue}")
        print(f"Component: {decision.diagnosis.component_id}")
        print(f"Diagnosis severity: {decision.diagnosis.severity.value}")
        print(f"Recommendation priority: {decision.recommendation.priority.value}")
        print(f"Description: {decision.diagnosis.description}")
        print(f"Predicted status without intervention: {decision.forecast.predicted_status}")
        print(f"Time to critical steps: {decision.forecast.time_to_critical_steps}")
        print(f"Time to failure steps: {decision.forecast.time_to_failure_steps}")
        print(f"Baseline risk score: {decision.forecast.risk_score:.2f}")
        print(f"Recommended action plan: {format_actions(decision.recommendation.actions)}")
        print(f"Expected effect: {decision.recommendation.expected_effect}")
        print("Evaluated alternatives:")

        for alternative in decision.recommendation.alternatives:
            print(
                f"- {format_actions(alternative.actions)}: "
                f"projected_status={alternative.predicted_status}, "
                f"projected_health={alternative.projected_health_index}, "
                f"risk_score={alternative.risk_score}, "
                f"expected_effect={alternative.expected_effect}"
            )

        print("Evidence:")

        for evidence in decision.diagnosis.evidence:
            print(
                f"- {evidence.timestamp} | {evidence.component_id} | "
                f"{evidence.field} = {evidence.value}"
            )


if __name__ == "__main__":
    main()