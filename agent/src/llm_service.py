import re
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
    """Generate a grounded LLM answer from agent analysis.

    @param run_id: Run identifier associated with the analysis.
    @param question: User question to answer.
    @param analysis: Structured agent analysis response.
    @param max_alternatives_per_decision: Maximum alternatives retained in full-context mode.
    @param provider: LLM provider name.
    @param model: Optional provider-specific model name.
    @param client: Optional preconstructed LLM client for tests or callers.
    @param mode: Generation mode, either rewrite or full-context answer.
    @return: LLM answer payload without internal prompt context.
    """
    llm_client = client or build_llm_client(provider=provider, model=model)

    if mode == "rewrite":
        source_summary = build_safe_summary(analysis)
        answer = to_plain_text(rewrite_or_return_source(llm_client, source_summary))

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
    answer = to_plain_text(llm_client.generate(messages))

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
    """Generate a grounded LLM answer and include the prompt context for inspection.

    @param run_id: Run identifier associated with the analysis.
    @param question: User question to answer.
    @param analysis: Structured agent analysis response.
    @param max_alternatives_per_decision: Maximum alternatives retained in full-context mode.
    @param provider: LLM provider name.
    @param model: Optional provider-specific model name.
    @param client: Optional preconstructed LLM client for tests or callers.
    @param mode: Generation mode, either rewrite or full-context answer.
    @return: LLM answer payload including context and messages when applicable.
    """
    llm_client = client or build_llm_client(provider=provider, model=model)

    if mode == "rewrite":
        source_summary = build_safe_summary(analysis)
        answer = to_plain_text(rewrite_or_return_source(llm_client, source_summary))

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
    answer = to_plain_text(llm_client.generate(messages))

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
    """Rewrite a deterministic summary when the client supports rewriting.

    @param llm_client: LLM client implementing generate and optionally rewrite.
    @param source_summary: Grounded deterministic source summary.
    @return: Rewritten summary, or the source summary when rewriting is unavailable.
    """
    rewrite = getattr(llm_client, "rewrite", None)

    if rewrite is None:
        return source_summary

    return rewrite(source_summary)


def to_plain_text(value: str) -> str:
    """Strip Markdown-like formatting from LLM output before API return.

    @param value: Raw LLM output.
    @return: Plain-text answer with simple lines and no Markdown markers.
    """
    text = str(value or "")
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("```", "")
    text = text.replace("__", "")
    text = re.sub(r"[*`#>]", "", text)

    lines = []
    for line in text.splitlines():
        cleaned = line.strip()
        cleaned = re.sub(r"^[-+]\s+", "", cleaned)
        cleaned = re.sub(r"^\d+[.)]\s+", "", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        lines.append(cleaned)

    return "\n".join(lines).strip()
