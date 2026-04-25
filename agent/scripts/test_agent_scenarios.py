import json
from pathlib import Path

from agent.src.decision import make_agent_decisions
from agent.src.explainer import explain_decisions
from agent.src.explainer import format_actions


def load_history(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def print_summary(scenario_name: str, decisions: list) -> None:
    print(f"\nScenario: {scenario_name}")
    print("-" * 80)

    if not decisions:
        print("No issues detected.")
        return

    for decision in decisions:
        print(
            f"{decision.diagnosis.component_id} | "
            f"issue={decision.diagnosis.issue} | "
            f"priority={decision.recommendation.priority.value} | "
            f"forecast={decision.forecast.predicted_status} | "
            f"plan={format_actions(decision.recommendation.actions)} | "
            f"risk={decision.recommendation.alternatives[0].risk_score}"
        )


def main() -> None:
    scenarios_dir = Path("data/agent_scenarios")
    horizon_steps = 24

    paths = sorted(scenarios_dir.glob("*.json"))

    if not paths:
        print("No scenario files found. Run: python -m agent.scripts.generate_synthetic_agent_scenarios")
        return

    for path in paths:
        history = load_history(path)
        run_id = history[-1]["run_id"]
        latest_record = history[-1]

        decisions = make_agent_decisions(
            run_id=run_id,
            latest_record=latest_record,
            history=history,
            horizon_steps=horizon_steps,
        )

        print_summary(path.stem, decisions)

    print("\nDetailed copilot output for most severe scenario")
    print("=" * 80)

    severe_path = scenarios_dir / "severe_thermal_risk.json"
    history = load_history(severe_path)
    run_id = history[-1]["run_id"]
    latest_record = history[-1]

    decisions = make_agent_decisions(
        run_id=run_id,
        latest_record=latest_record,
        history=history,
        horizon_steps=horizon_steps,
    )

    print(explain_decisions(decisions))


if __name__ == "__main__":
    main()