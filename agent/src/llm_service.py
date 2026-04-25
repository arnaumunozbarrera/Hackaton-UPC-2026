from typing import Any

from agent.src.llm_client import LLMClient, build_llm_client
from agent.src.llm_context import build_llm_context, build_llm_messages
from agent.src.safe_summary import build_safe_summary


def generate_llm_answer(
    run_id: str,
    question: str,
    analysis: dict[str, Any],
    max_alternatives_per_decision: int = 5,
    provider: str = "mock",
    model: str | None = None,
    client: LLMClient | None = None,
    mode: str = "rewrite",
) -> dict[str, Any]:
    llm_client = client or build_llm_client(provider=provider, model=model)

    if mode == "rewrite":
        source_summary = build_safe_summary(analysis)
        answer = rewrite_or_return_source(llm_client, source_summary)

        return {
            "run_id": run_id,
            "question": question,
            "provider": llm_client.provider,
            "model": llm_client.model,
            "mode": mode,
            "answer": answer,
            "source_summary": source_summary,
            "highest_priority": analysis["highest_priority"],
            "decision_count": analysis["decision_count"],
        }

    context = build_llm_context(
        run_id=run_id,
        question=question,
        analysis=analysis,
        max_alternatives_per_decision=max_alternatives_per_decision,
    )

    messages = build_llm_messages(context)
    answer = llm_client.generate(messages)

    return {
        "run_id": run_id,
        "question": question,
        "provider": llm_client.provider,
        "model": llm_client.model,
        "mode": mode,
        "answer": answer,
        "highest_priority": analysis["highest_priority"],
        "decision_count": analysis["decision_count"],
    }


def generate_llm_answer_with_context(
    run_id: str,
    question: str,
    analysis: dict[str, Any],
    max_alternatives_per_decision: int = 5,
    provider: str = "mock",
    model: str | None = None,
    client: LLMClient | None = None,
    mode: str = "rewrite",
) -> dict[str, Any]:
    llm_client = client or build_llm_client(provider=provider, model=model)

    if mode == "rewrite":
        source_summary = build_safe_summary(analysis)
        answer = rewrite_or_return_source(llm_client, source_summary)

        return {
            "run_id": run_id,
            "question": question,
            "provider": llm_client.provider,
            "model": llm_client.model,
            "mode": mode,
            "answer": answer,
            "source_summary": source_summary,
            "highest_priority": analysis["highest_priority"],
            "decision_count": analysis["decision_count"],
        }

    context = build_llm_context(
        run_id=run_id,
        question=question,
        analysis=analysis,
        max_alternatives_per_decision=max_alternatives_per_decision,
    )

    messages = build_llm_messages(context)
    answer = llm_client.generate(messages)

    return {
        "run_id": run_id,
        "question": question,
        "provider": llm_client.provider,
        "model": llm_client.model,
        "mode": mode,
        "answer": answer,
        "highest_priority": analysis["highest_priority"],
        "decision_count": analysis["decision_count"],
        "context": context,
        "messages": messages,
    }


def rewrite_or_return_source(llm_client: LLMClient, source_summary: str) -> str:
    rewrite = getattr(llm_client, "rewrite", None)

    if rewrite is None:
        return source_summary

    return rewrite(source_summary)