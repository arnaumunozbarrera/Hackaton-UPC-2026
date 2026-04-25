import json
from pathlib import Path

from agent.src.historian import JsonHistorian
from agent.src.service import analyze_scenario_response


def main() -> None:
    historian = JsonHistorian(Path("data/agent_scenarios"))

    response = analyze_scenario_response(
        historian=historian,
        scenario_name="severe_thermal_risk",
        horizon_steps=24,
    )

    output_path = Path("data/agent_response_example.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(response, file, indent=2)

    print(json.dumps(response, indent=2))
    print(f"\nSaved response at {output_path}")


if __name__ == "__main__":
    main()