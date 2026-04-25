from pathlib import Path

from agent.src.historian import JsonHistorian
from agent.src.query import answer_question
from agent.src.service import analyze_scenario_response


def main() -> None:
    historian = JsonHistorian(Path("data/agent_scenarios"))

    response = analyze_scenario_response(
        historian=historian,
        scenario_name="severe_thermal_risk",
        horizon_steps=24,
    )

    questions = [
        "What is the current status?",
        "What should we do?",
        "What happens if we continue like this?",
        "Why do you recommend this?",
        "Show me the alternatives",
    ]

    for question in questions:
        print("\nUser question")
        print("-" * 80)
        print(question)

        print("\nCopilot answer")
        print("-" * 80)
        print(answer_question(response, question))


if __name__ == "__main__":
    main()