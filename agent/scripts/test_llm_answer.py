from pathlib import Path

from agent.src.llm_service import generate_llm_answer_with_context
from agent.src.service import analyze_scenario_response
from agent.src.sqlite_historian import SQLiteHistorian


def main() -> None:
    historian = SQLiteHistorian(Path("backend/storage/historian.sqlite"))
    run_id = "run_1777083541387"
    question = "Why do you recommend this maintenance plan?"

    analysis = analyze_scenario_response(
        historian=historian,
        scenario_name=run_id,
        horizon_steps=24,
    )

    response = generate_llm_answer_with_context(
        run_id=run_id,
        question=question,
        analysis=analysis,
        max_alternatives_per_decision=3,
    )

    print(response["answer"])


if __name__ == "__main__":
    main()