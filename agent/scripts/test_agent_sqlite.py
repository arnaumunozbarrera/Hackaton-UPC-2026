from pathlib import Path

from agent.src.explainer import explain_decisions
from agent.src.explainer import format_actions
from agent.src.planner import find_selected_evaluation
from agent.src.service import analyze_scenario
from agent.src.sqlite_historian import SQLiteHistorian


def print_runs(historian: SQLiteHistorian) -> None:
    runs = historian.list_runs()

    print("Available runs")
    print("=" * 80)

    for run in runs:
        print(
            f"{run['run_id']} | scenario={run['scenario_id']} | "
            f"created_at={run['created_at']} | total_usages={run['total_usages']} | "
            f"usage_step={run['usage_step']}"
        )


def print_latest_health(historian: SQLiteHistorian, run_id: str) -> None:
    latest = historian.get_latest_record(run_id)

    print("Latest component health")
    print("-" * 80)

    for component_id, component in latest["components"].items():
        print(
            f"{component_id}: health={component['health_index']:.4f}, "
            f"status={component['status']}"
        )


def print_summary(run_id: str, decisions: list) -> None:
    print(f"\nRun: {run_id}")
    print("=" * 80)

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
    db_path = Path("backend/storage/historian.sqlite")
    historian = SQLiteHistorian(db_path)
    runs = historian.list_runs()
    horizon_steps = 24

    print_runs(historian)

    if not runs:
        print("No runs found.")
        return

    for run in runs:
        run_id = run["run_id"]
        decisions = analyze_scenario(
            historian=historian,
            scenario_name=run_id,
            horizon_steps=horizon_steps,
            history_window_steps=None,
        )

        print_summary(run_id, decisions)
        print_latest_health(historian, run_id)

    most_interesting_run = max(
        runs,
        key=lambda run: float(run["total_usages"] or 0.0),
    )

    run_id = most_interesting_run["run_id"]
    decisions = analyze_scenario(
        historian=historian,
        scenario_name=run_id,
        horizon_steps=horizon_steps,
        history_window_steps=None,
    )

    print("\nDetailed copilot output for longest run")
    print("=" * 80)
    print(f"Run: {run_id}")
    print(explain_decisions(decisions))


if __name__ == "__main__":
    main()