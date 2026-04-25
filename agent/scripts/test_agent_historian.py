from pathlib import Path

from agent.src.explainer import explain_decisions
from agent.src.explainer import format_actions
from agent.src.historian import JsonHistorian
from agent.src.planner import find_selected_evaluation
from agent.src.service import analyze_scenario


def print_summary(scenario_name: str, decisions: list) -> None:
    print(f"\nScenario: {scenario_name}")
    print("-" * 80)

    if not decisions:
        print("No issues detected.")
        return

    for decision in decisions:
        selected = find_selected_evaluation(decision.recommendation)

        print(
            f"{decision.diagnosis.component_id} | "
            f"issue={decision.diagnosis.issue} | "
            f"priority={decision.recommendation.priority.value} | "
            f"forecast={decision.forecast.predicted_status} | "
            f"plan={format_actions(decision.recommendation.actions)} | "
            f"selected_risk={selected.risk_score} | "
            f"projected_status={selected.predicted_status} | "
            f"projected_health={selected.projected_health_index}"
        )


def main() -> None:
    historian = JsonHistorian(Path("data/agent_scenarios"))
    scenarios = historian.list_scenarios()
    horizon_steps = 24

    if not scenarios:
        print("No scenarios found. Run: python -m agent.scripts.generate_synthetic_agent_scenarios")
        return

    for scenario_name in scenarios:
        decisions = analyze_scenario(
            historian=historian,
            scenario_name=scenario_name,
            horizon_steps=horizon_steps,
        )

        print_summary(scenario_name, decisions)

    print("\nDetailed copilot output for most severe scenario")
    print("=" * 80)

    decisions = analyze_scenario(
        historian=historian,
        scenario_name="severe_thermal_risk",
        horizon_steps=horizon_steps,
    )

    print(explain_decisions(decisions))


if __name__ == "__main__":
    main()