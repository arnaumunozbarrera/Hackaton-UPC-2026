import json
from pathlib import Path

from agent.src.llm_context import build_llm_context
from agent.src.llm_context import build_llm_messages
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

    context = build_llm_context(
        run_id=run_id,
        question=question,
        analysis=analysis,
    )

    messages = build_llm_messages(context)

    output_path = Path("data/agent_llm_context_example.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "context": context,
                "messages": messages,
            },
            file,
            indent=2,
        )

    print(json.dumps(context, indent=2))
    print(f"\nSaved LLM context at {output_path}")


if __name__ == "__main__":
    main()