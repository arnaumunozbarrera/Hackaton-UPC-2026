"""Grounded chatbot for historian-backed queries."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from app.storage import historian


STATUS_KEYWORDS = ("status", "state", "health", "current", "now", "condition")
TREND_KEYWORDS = ("trend", "evolution", "change", "degradation", "degrade", "worsen", "improve")
PREDICTION_KEYWORDS = ("predict", "prediction", "forecast", "future", "fail", "failure", "critical")
MESSAGE_KEYWORDS = ("message", "event", "alert", "alerts", "issue", "issues", "warning", "warnings")
DRIVER_KEYWORDS = ("driver", "drivers", "temperature", "humidity", "load", "contamination", "maintenance")
PARAMETER_KEYWORDS = ("parameter", "parameters", "modify", "change", "adjust", "increase", "decrease", "effect", "affect")
REPLACEMENT_KEYWORDS = ("replace", "replacement", "replaced", "swap", "change out")
SUPPORTED_TOPIC_KEYWORDS = {
    "status": STATUS_KEYWORDS,
    "trend": TREND_KEYWORDS,
    "prediction": PREDICTION_KEYWORDS,
    "events": MESSAGE_KEYWORDS,
    "drivers": DRIVER_KEYWORDS,
    "parameters": PARAMETER_KEYWORDS,
    "replacement": REPLACEMENT_KEYWORDS,
}
MIN_TOPIC_MATCH_SCORE = 0.34
COMPONENT_ALIASES = {
    "recoater_blade": ("recoater blade", "blade", "recoater"),
    "nozzle_plate": ("nozzle plate", "nozzle", "plate"),
    "heating_elements": ("heating elements", "heater", "heating"),
    "thermal_firing_resistors": ("thermal firing resistors", "resistors", "firing resistors"),
    "cleaning_interface": ("cleaning interface", "cleaner", "cleaning"),
    "temperature_sensors": ("temperature sensors", "temperature sensor", "sensor", "sensors"),
}


@dataclass
class GroundedContext:
    run_id: str | None
    scenario_id: str | None
    component_id: str | None
    question: str
    available: bool
    sufficient_data: bool
    facts: list[str]
    evidence: list[dict[str, Any]]
    summary: str
    metadata: dict[str, Any]
    llm_context: dict[str, Any]
    support_metrics: list[dict[str, Any]]
    action_options: list[dict[str, Any]]
    matched_topics: list[dict[str, Any]]


def answer_chat_question(question: str, run_id: str | None = None, component_id: str | None = None) -> dict[str, Any]:
    normalized_question = " ".join((question or "").strip().split())
    topic_match = _match_supported_topics(normalized_question)

    if not topic_match["is_relevant"]:
        return {
            "answer": "I cannot answer that reliably with the available historian context. Ask about component status, degradation, alerts, prediction, replacement timing, operating conditions, or action options.",
            "facts": [],
            "evidence": [],
            "run_id": None,
            "scenario_id": None,
            "component_id": None,
            "grounded": True,
            "insufficient_data": True,
            "model": {"provider": "deterministic", "name": "relevance-gate"},
            "support_metrics": [],
            "action_options": [],
            "matched_topics": topic_match["matches"],
        }

    context = _build_grounded_context(normalized_question, run_id=run_id, component_id=component_id)

    if not context.available:
        return {
            "answer": "There is no stored simulation run yet, so I cannot provide a grounded explanation of the component behavior.",
            "facts": [],
            "evidence": [],
            "run_id": None,
            "scenario_id": None,
            "component_id": None,
            "grounded": True,
            "insufficient_data": True,
            "model": {"provider": "deterministic", "name": "grounded-fallback"},
            "support_metrics": [],
            "action_options": [],
            "matched_topics": topic_match["matches"],
        }

    model_output = _generate_grounded_llm_answer(context)
    answer = model_output["answer"] if model_output else _build_narrative_fallback(context)
    model_info = model_output["model"] if model_output else {"provider": "deterministic", "name": "grounded-fallback"}

    return {
        "answer": answer,
        "facts": context.facts,
        "evidence": context.evidence,
        "run_id": context.run_id,
        "scenario_id": context.scenario_id,
        "component_id": context.component_id,
        "grounded": True,
        "insufficient_data": not context.sufficient_data,
        "model": model_info,
        "metadata": context.metadata,
        "support_metrics": context.support_metrics,
        "action_options": context.action_options,
        "matched_topics": context.matched_topics,
    }


def _build_grounded_context(question: str, run_id: str | None, component_id: str | None) -> GroundedContext:
    topic_match = _match_supported_topics(question)
    target_run_id = run_id or (historian.get_latest_run() or {}).get("run_id")
    if not target_run_id:
        return GroundedContext(
            run_id=None,
            scenario_id=None,
            component_id=None,
            question=question,
            available=False,
            sufficient_data=False,
            facts=[],
            evidence=[],
            summary="No run data is available.",
            metadata={},
            llm_context={},
            support_metrics=[],
            action_options=[],
            matched_topics=topic_match["matches"],
        )

    timeline = historian.get_run_timeline(target_run_id)
    if not timeline:
        return GroundedContext(
            run_id=target_run_id,
            scenario_id=None,
            component_id=None,
            question=question,
            available=False,
            sufficient_data=False,
            facts=[],
            evidence=[],
            summary="No timeline data is available for the requested run.",
            metadata={},
            llm_context={},
            support_metrics=[],
            action_options=[],
            matched_topics=topic_match["matches"],
        )

    latest_point = timeline[-1]
    inferred_component_id = component_id or _infer_component_id(question, latest_point)
    run_metadata = next((run for run in historian.list_runs() if run["run_id"] == target_run_id), None) or {}
    messages = historian.get_messages(target_run_id)
    facts: list[str] = []
    evidence: list[dict[str, Any]] = []
    metadata = {
        "latest_usage_count": latest_point["usage_count"],
        "latest_timestamp": latest_point["timestamp"],
        "message_count": len(messages),
    }
    llm_context: dict[str, Any] = {
        "question": question,
        "scenario_id": latest_point["scenario_id"],
        "component_id": inferred_component_id,
        "latest_timestamp": latest_point["timestamp"],
        "latest_usage_count": latest_point["usage_count"],
        "drivers": latest_point["drivers"],
        "messages": [],
        "prediction": None,
        "component": None,
    }
    support_metrics = _build_support_metrics(latest_point=latest_point, component_id=inferred_component_id)
    action_options: list[dict[str, Any]] = []

    facts.append("The explanation is based on the latest stored scenario for this machine.")
    facts.append("The latest stored observation reflects the most recent machine behavior in this scenario.")
    facts.append(
        "The machine was running under a specific combination of load, contamination, humidity, thermal stress, "
        "and maintenance conditions."
    )
    evidence.append(
        {
            "type": "run",
            "run_id": target_run_id,
            "scenario_id": latest_point["scenario_id"],
            "timestamp": latest_point["timestamp"],
            "usage_count": latest_point["usage_count"],
        }
    )

    if inferred_component_id and inferred_component_id in latest_point["components"]:
        component_history = historian.get_component_history(target_run_id, inferred_component_id)
        component_summary = _summarize_component_history(component_history, inferred_component_id)
        prediction = historian.get_latest_prediction(target_run_id, inferred_component_id)
        component_messages = [message for message in messages if message.get("component_id") == inferred_component_id]

        facts.extend(component_summary["facts"])
        evidence.extend(component_summary["evidence"])
        metadata["component_points"] = len(component_history)
        llm_context["component"] = component_summary["llm_component"]
        action_options = _build_action_options(
            component_id=inferred_component_id,
            component=latest_point["components"][inferred_component_id],
            prediction=prediction,
        )
        llm_context["action_options"] = action_options

        if prediction:
            prediction_fact = _prediction_fact(prediction)
            if prediction_fact:
                facts.append(prediction_fact)
                evidence.append(
                    {
                        "type": "prediction",
                        "component_id": inferred_component_id,
                        "payload": prediction,
                    }
                )
            llm_context["prediction"] = prediction

        for message in component_messages[:3]:
            facts.append(
                f"At {message['timestamp']}, the system recorded a {message['severity'].lower()} event for {inferred_component_id}: "
                f"{message['title']}."
            )
            evidence.append(
                {
                    "type": "message",
                    "component_id": inferred_component_id,
                    "timestamp": message["timestamp"],
                    "severity": message["severity"],
                    "title": message["title"],
                    "body": message["body"],
                }
            )
        llm_context["messages"] = [
            {
                "severity": message["severity"],
                "title": message["title"],
                "body": message["body"],
                "timestamp": message["timestamp"],
            }
            for message in component_messages[:3]
        ]

    elif inferred_component_id:
        facts.append(f"The requested component does not appear in the latest stored run.")

    summary, sufficient_data = _compose_summary(
        question=question,
        run_metadata=run_metadata,
        latest_point=latest_point,
        component_id=inferred_component_id,
        facts=facts,
        messages=messages,
        evidence=evidence,
    )

    return GroundedContext(
        run_id=target_run_id,
        scenario_id=latest_point["scenario_id"],
        component_id=inferred_component_id,
        question=question,
        available=True,
        sufficient_data=sufficient_data,
        facts=facts,
        evidence=evidence,
        summary=summary,
        metadata=metadata,
        llm_context=llm_context,
        support_metrics=support_metrics,
        action_options=action_options,
        matched_topics=topic_match["matches"],
    )


def _summarize_component_history(component_history: list[dict], component_id: str) -> dict[str, Any]:
    if not component_history:
        return {
            "facts": [f"There is no stored history available for {component_id}."],
            "evidence": [],
            "llm_component": None,
        }

    latest_component = component_history[-1]["components"][component_id]
    first_component = component_history[0]["components"][component_id]
    latest_health = float(latest_component["health_index"])
    initial_health = float(first_component["health_index"])
    health_delta = round(latest_health - initial_health, 6)
    facts = [
        f"{component_id} is currently in a {latest_component['status'].lower()} condition.",
        f"There are enough stored observations to compare how {component_id} evolved over time.",
        f"The stored history shows a clear change in condition over time, rather than an isolated point.",
    ]

    metrics = latest_component.get("metrics", {})
    for metric_name, metric_value in sorted(metrics.items())[:4]:
        if metric_value is not None:
            facts.append(
                f"The latest record for {component_id} includes changes in {metric_name.replace('_', ' ')}."
            )

    damage = latest_component.get("damage", {})
    for damage_name, damage_value in sorted(damage.items())[:4]:
        if damage_value is not None and damage_value > 0:
            facts.append(
                f"The latest record shows visible impact from {damage_name.replace('_', ' ')} in {component_id}."
            )

    alerts = latest_component.get("alerts", [])
    if alerts:
        facts.append(f"The latest record also includes alert activity related to {component_id}.")

    evidence = [
        {
            "type": "component_state",
            "component_id": component_id,
            "timestamp": component_history[-1]["timestamp"],
            "usage_count": component_history[-1]["usage_count"],
            "status": latest_component["status"],
            "health_index": latest_component["health_index"],
            "metrics": latest_component.get("metrics", {}),
            "damage": latest_component.get("damage", {}),
            "alerts": latest_component.get("alerts", []),
        }
    ]
    llm_component = {
        "component_id": component_id,
        "current_status": latest_component["status"],
        "current_health_index": latest_health,
        "initial_health_index": initial_health,
        "health_delta": health_delta,
        "observation_count": len(component_history),
        "first_timestamp": component_history[0]["timestamp"],
        "latest_timestamp": component_history[-1]["timestamp"],
        "latest_metrics": latest_component.get("metrics", {}),
        "latest_damage": latest_component.get("damage", {}),
        "latest_alerts": latest_component.get("alerts", []),
    }
    return {"facts": facts, "evidence": evidence, "llm_component": llm_component}


def _compose_summary(
    question: str,
    run_metadata: dict[str, Any],
    latest_point: dict[str, Any],
    component_id: str | None,
    facts: list[str],
    messages: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> tuple[str, bool]:
    lower_question = question.lower()

    if component_id and component_id not in latest_point["components"]:
        return (
            f"I cannot provide a grounded explanation for {component_id} because it does not appear in the stored run.",
            False,
        )

    if any(keyword in lower_question for keyword in MESSAGE_KEYWORDS):
        if not messages:
            return (
                "The stored data does not include runtime messages for this run, so the explanation is limited to the observed component behavior over time.",
                True,
            )
        return (
            "The stored data includes repeated event activity, which suggests the system was tracking persistent abnormal behavior rather than a single isolated issue.",
            True,
        )

    if any(keyword in lower_question for keyword in DRIVER_KEYWORDS):
        return (
            "The stored data suggests that the component behavior evolved under changing operating conditions, especially load, contamination, humidity, thermal stress, and maintenance level. "
            "Those conditions help explain why degradation accumulated over time instead of appearing as a one-off event.",
            True,
        )

    if any(keyword in lower_question for keyword in PARAMETER_KEYWORDS):
        parameter_effects = _describe_parameter_effects(component_id, latest_point)
        return (parameter_effects, True)

    if any(keyword in lower_question for keyword in REPLACEMENT_KEYWORDS):
        return (
            _describe_replacement_timing(
                component_id=component_id,
                latest_point=latest_point,
                facts=facts,
            ),
            True,
        )

    if any(keyword in lower_question for keyword in PREDICTION_KEYWORDS):
        prediction_fact = next((fact for fact in facts if fact.startswith("Latest prediction")), None)
        if prediction_fact:
            return (prediction_fact, True)
        return (
            "There is no stored prediction for the requested scope, so the explanation can only rely on the observed progression captured in the stored records.",
            False,
        )

    if any(keyword in lower_question for keyword in TREND_KEYWORDS):
        if component_id:
            return (
                f"The stored data shows that {component_id} degraded progressively over time rather than changing abruptly in a single step. "
                "The overall pattern reflects accumulated stress across the run.",
                True,
            )
        return (
            "There is not enough stored component history to describe a clear progression over time.",
            False,
        )

    if component_id and any(keyword in lower_question for keyword in STATUS_KEYWORDS):
        return (
            f"The latest stored records show the current condition of {component_id}, and that condition should be read as the result of an evolving pattern rather than an isolated measurement.",
            True,
        )

    if not evidence:
        return ("I do not have sufficient relevant data to explain this reliably.", False)

    general_summary = "The stored data supports a grounded explanation of the component behavior over time."
    if component_id:
        general_summary += (
            f" For {component_id}, the records suggest a gradual progression shaped by operating conditions, component-level changes, and any related alert activity."
        )
    return (general_summary, True)


def _generate_grounded_llm_answer(context: GroundedContext) -> dict[str, Any] | None:
    if not context.sufficient_data or not context.llm_context:
        return None

    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model_name = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    if not _ollama_is_available(base_url):
        return None

    prompt = (
        "You are an industrial components expert.\n"
        "Write a brief, human explanation that answers the user's question.\n"
        "Use only the grounded historian context provided below.\n"
        "Explain the current context, the evolution of the problem over time, and the impact on the component when supported by the data.\n"
        "If the question is about changing parameters, explain how the recorded operating conditions relate to the observed behavior, but do not invent causal claims beyond the supplied data.\n"
        "Do not mention databases, raw fields, JSON, identifiers, run ids, or internal variable names.\n"
        "Avoid raw dumps and avoid saying 'facts'.\n"
        "Write in 2 or 3 short paragraphs, similar to a human technical explanation.\n"
        "Do not reuse a fixed template. Vary the structure, sentence openings, and transitions from one answer to another.\n"
        "Comment on the main points of interest, such as the most relevant metric changes, repeated alerts, visible damage patterns, unusual operating conditions, or the final component state.\n"
        "If the component is failed, critical, degraded, or stable, adapt the tone and structure to that progression instead of using the same wording every time.\n"
        "When metrics are available, mention the most relevant ones in natural language rather than listing every value mechanically.\n"
        "If the question asks when a component should be replaced, explain the replacement timing in relation to the current state, recent trend, alerts, and any available prediction context.\n"
        "If action options are provided, you may mention them as possible next steps, but do not claim that one option is selected unless the context clearly supports it.\n"
        "Do not exaggerate certainty, and do not invent metrics or causes that are not in the supplied context.\n"
        "Keep it concise, natural, and professional.\n"
        "If the context is not enough to answer reliably, reply exactly with INSUFFICIENT_DATA.\n\n"
        f"User question: {context.question}\n"
        f"Grounded context: {json.dumps(context.llm_context, ensure_ascii=True)}\n"
    )

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 220,
        },
    }

    try:
        raw_response = _ollama_post(base_url, "/api/generate", payload)
    except OSError:
        return None

    answer = str(raw_response.get("response", "")).strip()
    if not answer or answer == "INSUFFICIENT_DATA":
        return None

    return {
        "answer": answer,
        "model": {
            "provider": "ollama",
            "name": model_name,
        },
    }


def _build_narrative_fallback(context: GroundedContext) -> str:
    component = context.llm_context.get("component") or {}
    component_id = context.component_id or "the component"
    messages = context.llm_context.get("messages") or []
    prediction = context.llm_context.get("prediction")

    if not component:
        return context.summary

    status = str(component.get("current_status", "UNKNOWN")).upper()
    metric_interest = _interesting_metric_phrases(component.get("latest_metrics") or {})
    damage_interest = _interesting_damage_phrases(component.get("latest_damage") or {})
    alert_sentence = _build_alert_sentence(messages, component.get("latest_alerts") or [])
    progression_sentence = _build_progression_sentence(component_id, status, metric_interest, damage_interest)
    interest_sentence = _build_interest_sentence(metric_interest, damage_interest, alert_sentence)
    latest_timestamp = component.get("latest_timestamp") or context.metadata.get("latest_timestamp")
    paragraph_three = _build_latest_state_sentence(component_id, status, latest_timestamp, prediction)
    if prediction:
        paragraph_three += " " + _build_prediction_sentence(status)

    paragraphs = [progression_sentence]
    if interest_sentence:
        paragraphs.append(interest_sentence)
    paragraphs.append(paragraph_three)
    return "\n\n".join(paragraphs)


def _ollama_is_available(base_url: str) -> bool:
    try:
        _ollama_post(base_url, "/api/tags", None, method="GET")
        return True
    except OSError:
        return False


def _ollama_post(base_url: str, path: str, payload: dict[str, Any] | None, method: str = "POST") -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=1.5) as response:
            return json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        raise OSError("Ollama request failed") from exc


def _match_supported_topics(question: str) -> dict[str, Any]:
    normalized_question = question.lower().strip()
    tokens = set(_tokenize(normalized_question))
    matches = []

    for topic, keywords in SUPPORTED_TOPIC_KEYWORDS.items():
        score = _topic_similarity_score(normalized_question, tokens, keywords)
        if score > 0:
            matches.append({"topic": topic, "score": round(score, 3)})

    matches.sort(key=lambda item: item["score"], reverse=True)
    best_score = matches[0]["score"] if matches else 0.0

    has_component_hint = any(
        alias in normalized_question
        for aliases in COMPONENT_ALIASES.values()
        for alias in aliases
    ) or any(component in normalized_question for component in COMPONENT_ALIASES)

    return {
        "matches": matches[:3],
        "best_score": best_score,
        "is_relevant": best_score >= MIN_TOPIC_MATCH_SCORE or (best_score >= 0.22 and has_component_hint),
    }


def _topic_similarity_score(question: str, question_tokens: set[str], keywords: tuple[str, ...]) -> float:
    best = 0.0
    for keyword in keywords:
        keyword_tokens = set(_tokenize(keyword))
        if not keyword_tokens:
            continue

        overlap = len(question_tokens & keyword_tokens)
        token_score = overlap / len(keyword_tokens)
        phrase_bonus = 0.25 if keyword in question else 0.0
        starts_bonus = 0.1 if any(token.startswith(prefix) for token in question_tokens for prefix in keyword_tokens) else 0.0
        score = min(token_score + phrase_bonus + starts_bonus, 1.0)
        best = max(best, score)
    return best


def _tokenize(text: str) -> list[str]:
    cleaned = []
    current = []
    for char in text:
        if char.isalnum() or char == "_":
            current.append(char)
        elif current:
            cleaned.append("".join(current))
            current = []
    if current:
        cleaned.append("".join(current))
    return cleaned


def _infer_component_id(question: str, latest_point: dict[str, Any]) -> str | None:
    component_ids = latest_point.get("components", {}).keys()
    normalized_question = question.lower()
    for component_id in component_ids:
        if component_id.lower() in normalized_question:
            return component_id
    for component_id in component_ids:
        for alias in COMPONENT_ALIASES.get(component_id, ()):
            if alias in normalized_question:
                return component_id
    for component_id in component_ids:
        tokens = component_id.lower().split("_")
        if any(token and token in normalized_question for token in tokens):
            return component_id
    return None


def _prediction_fact(prediction: dict[str, Any]) -> str | None:
    if not prediction:
        return None

    if "predicted_status" in prediction:
        return (
            "The latest prediction suggests that this component may continue moving toward a more critical state if conditions stay the same."
        )

    if "prediction" in prediction:
        return "There is stored prediction data for this component, but it only supports a cautious explanation rather than a precise forecast in natural language."

    return "There is stored prediction data for this component, but it does not support a more detailed natural-language forecast."


def _build_support_metrics(latest_point: dict[str, Any], component_id: str | None) -> list[dict[str, Any]]:
    ranked_metrics: list[tuple[int, dict[str, Any]]] = []

    for driver_name, driver_value in latest_point.get("drivers", {}).items():
        metric = _format_metric_entry(driver_name, driver_value, scope="Operating condition")
        if metric:
            ranked_metrics.append((_metric_priority(driver_name, metric["value"], "Operating condition"), metric))

    if component_id:
        component = latest_point.get("components", {}).get(component_id)
        if component:
            health_metric = _metric_entry("Component health", component.get("health_index"), "index", "Component")
            ranked_metrics.append((_metric_priority("health_index", health_metric["value"], "Component"), health_metric))

            for metric_name, metric_value in component.get("metrics", {}).items():
                formatted = _format_metric_entry(metric_name, metric_value, scope="Component")
                if formatted:
                    ranked_metrics.append((_metric_priority(metric_name, formatted["value"], "Component"), formatted))

    ranked_metrics.sort(key=lambda item: item[0], reverse=True)
    return [metric for _, metric in ranked_metrics[:3]]


def _build_action_options(component_id: str, component: dict[str, Any], prediction: dict[str, Any] | None) -> list[dict[str, Any]]:
    status = str(component.get("status", "UNKNOWN")).upper()
    options: list[dict[str, Any]] = []

    if status in {"FAILED", "CRITICAL"}:
        options.append(
            _action_option(
                option_id="replace_component",
                label="Replace component",
                priority="high",
                rationale=f"{component_id} is already {status.lower()} or close to failure in the stored state.",
            )
        )

    options.append(
        _action_option(
            option_id="schedule_maintenance",
            label="Schedule maintenance",
            priority="medium" if status == "DEGRADED" else "high",
            rationale="Maintenance is a low-regret option when degradation is visible in the stored history.",
        )
    )

    options.append(
        _action_option(
            option_id="reduce_operating_load",
            label="Reduce operating load",
            priority="medium",
            rationale="Lowering stress conditions may slow further degradation while the component is still in service.",
        )
    )

    if prediction and prediction.get("predicted_failure_timestamp"):
        options[0 if status in {"FAILED", "CRITICAL"} else 1]["forecast_hint"] = (
            f"Predicted failure timing is around {prediction['predicted_failure_timestamp']}."
        )

    return options[:3]


def _action_option(option_id: str, label: str, priority: str, rationale: str) -> dict[str, Any]:
    return {
        "id": option_id,
        "label": label,
        "priority": priority,
        "rationale": rationale,
    }


def _format_metric_entry(metric_name: str, metric_value: Any, scope: str) -> dict[str, Any] | None:
    if metric_value is None:
        return None

    config = _metric_config(metric_name)
    value = float(metric_value) if isinstance(metric_value, (int, float)) else metric_value

    if isinstance(value, float) and config["transform"] == "percent":
        value = value * 100 if value <= 1 else value

    return _metric_entry(config["label"], value, config["unit"], scope)


def _metric_entry(label: str, value: Any, unit: str, scope: str) -> dict[str, Any]:
    return {
        "label": label,
        "value": round(float(value), 2) if isinstance(value, (int, float)) else value,
        "unit": unit,
        "scope": scope,
    }


def _metric_config(metric_name: str) -> dict[str, str]:
    configs = {
        "operational_load": {"label": "Operational load", "unit": "index", "transform": "raw"},
        "contamination": {"label": "Contamination", "unit": "index", "transform": "raw"},
        "humidity": {"label": "Humidity", "unit": "index", "transform": "raw"},
        "temperature_stress": {"label": "Thermal stress", "unit": "index", "transform": "raw"},
        "maintenance_level": {"label": "Maintenance level", "unit": "index", "transform": "raw"},
        "health_index": {"label": "Health", "unit": "index", "transform": "raw"},
        "blocked_nozzles_pct": {"label": "Blocked nozzles", "unit": "%", "transform": "percent"},
        "clogging_ratio": {"label": "Clogging ratio", "unit": "ratio", "transform": "raw"},
        "cleaning_interface_health": {"label": "Cleaning interface health", "unit": "index", "transform": "raw"},
        "contamination_factor": {"label": "Contamination factor", "unit": "factor", "transform": "raw"},
    }
    default_label = metric_name.replace("_", " ").title()
    return configs.get(metric_name, {"label": default_label, "unit": "value", "transform": "raw"})


def _metric_priority(metric_name: str, metric_value: Any, scope: str) -> int:
    try:
        value = float(metric_value)
    except (TypeError, ValueError):
        value = 0.0

    base_weights = {
        "blocked_nozzles_pct": 100,
        "clogging_ratio": 96,
        "cleaning_interface_health": 94,
        "contamination_factor": 92,
        "health_index": 90,
        "effective_load": 84,
        "decay_lambda": 82,
        "resistor_temperature_c": 80,
        "sensor_drift": 78,
        "temperature_stress": 74,
        "operational_load": 72,
        "contamination": 70,
        "humidity": 66,
        "maintenance_level": 64,
    }

    weight = base_weights.get(metric_name, 50)
    if scope == "Component":
        weight += 12

    if metric_name in {"cleaning_interface_health", "health_index", "maintenance_level"}:
        severity = (1 - max(0.0, min(value, 1.0))) * 100
    elif metric_name == "blocked_nozzles_pct":
        severity = max(0.0, value)
    else:
        severity = max(0.0, value * 100 if value <= 1 else value)

    return int(weight + round(severity))


def _describe_parameter_effects(component_id: str | None, latest_point: dict[str, Any]) -> str:
    component_text = component_id if component_id else "the observed components"
    active_drivers = latest_point.get("drivers", {})
    influences = []

    if active_drivers.get("operational_load", 0) > 0:
        influences.append("load")
    if active_drivers.get("temperature_stress", 0) > 0:
        influences.append("temperature")
    if active_drivers.get("humidity", 0) > 0:
        influences.append("humidity")
    if active_drivers.get("contamination", 0) > 0:
        influences.append("contamination")
    if active_drivers.get("maintenance_level", 0) > 0:
        influences.append("maintenance")

    if not influences:
        return (
            f"There is not enough operating-condition data to explain how parameter changes could affect {component_text}."
        )

    joined = ", ".join(influences[:-1]) + (f" and {influences[-1]}" if len(influences) > 1 else influences[0])
    return (
        f"The stored data shows progressive degradation in {component_text} under the recorded operating conditions. "
        f"If parameters such as {joined} change, the observed progression could also shift, affecting how quickly the condition worsens and how alert activity appears over time."
    )


def _describe_replacement_timing(component_id: str | None, latest_point: dict[str, Any], facts: list[str]) -> str:
    if not component_id:
        return "I need a specific component to explain replacement timing. Ask about a component such as the recoater blade or nozzle plate."

    component = latest_point.get("components", {}).get(component_id)
    if not component:
        return f"I cannot determine replacement timing for {component_id} because it is not present in the latest stored run."

    status = str(component.get("status", "UNKNOWN")).upper()
    component_name = component_id.replace("_", " ")

    if status == "FAILED":
        return f"{component_name.capitalize()} should already be considered for replacement, because the latest stored record shows it in a failed condition."
    if status == "CRITICAL":
        return f"{component_name.capitalize()} should be replaced as soon as possible, because the latest stored record shows it in a critical condition with very little remaining margin."
    if status == "DEGRADED":
        return f"{component_name.capitalize()} is not yet at confirmed failure, but the stored trend suggests replacement should be prepared if the current degradation pattern continues or alert activity increases."
    return f"{component_name.capitalize()} does not yet appear to require immediate replacement from the stored records, but it should continue to be monitored for degradation and alert escalation."


def _interesting_metric_phrases(metrics: dict[str, Any]) -> list[str]:
    phrases = []
    priority = [
        ("blocked_nozzles_pct", "blocked nozzle percentage"),
        ("clogging_ratio", "clogging ratio"),
        ("cleaning_interface_health", "cleaning interface health"),
        ("contamination_factor", "contamination factor"),
        ("effective_load", "effective load"),
        ("decay_lambda", "thermal decay response"),
        ("resistor_temperature_c", "resistor temperature"),
        ("sensor_drift", "sensor drift"),
    ]
    for key, label in priority:
        if key in metrics:
            phrases.append(label)
    for key in metrics:
        if len(phrases) >= 4:
            break
        label = key.replace("_", " ")
        if label not in phrases and key not in {item[0] for item in priority}:
            phrases.append(label)
    return phrases[:4]


def _interesting_damage_phrases(damage: dict[str, Any]) -> list[str]:
    phrases = []
    priority = [
        ("contamination_deposits", "contamination deposits"),
        ("electrical_fatigue", "electrical fatigue"),
        ("thermal_fatigue", "thermal fatigue"),
        ("wear", "mechanical wear"),
        ("corrosion", "corrosion"),
        ("clogging", "clogging buildup"),
    ]
    for key, label in priority:
        if key in damage and damage.get(key):
            phrases.append(label)
    for key, value in damage.items():
        if len(phrases) >= 3:
            break
        if value and key not in {item[0] for item in priority}:
            phrases.append(key.replace("_", " "))
    return phrases[:3]


def _build_alert_sentence(messages: list[dict[str, Any]], alerts: list[Any]) -> str:
    if messages:
        return "Alert activity appears repeatedly in the stored records, which points to a persistent issue rather than an isolated event."
    if alerts:
        return "The latest state also includes alert activity worth monitoring."
    return ""


def _build_progression_sentence(
    component_id: str,
    status: str,
    metric_interest: list[str],
    damage_interest: list[str],
) -> str:
    component_name = component_id.replace("_", " ")
    if status == "FAILED":
        opener = f"{component_name.capitalize()} followed a deteriorating path through the stored observations and eventually reached failure."
    elif status == "CRITICAL":
        opener = f"{component_name.capitalize()} shows a severe deterioration pattern and is now in a critical state."
    elif status == "DEGRADED":
        opener = f"{component_name.capitalize()} shows a clear degradation trend rather than normal variation."
    else:
        opener = f"{component_name.capitalize()} remains trackable through the stored observations, with changes that help explain its current condition."

    details = []
    if metric_interest:
        details.append("the main points of interest are " + _human_join(metric_interest))
    if damage_interest:
        details.append("the degradation pattern also reflects " + _human_join(damage_interest))

    if details:
        return opener + " In this case, " + "; ".join(details) + "."
    return opener


def _build_interest_sentence(
    metric_interest: list[str],
    damage_interest: list[str],
    alert_sentence: str,
) -> str:
    clauses = []
    if metric_interest:
        clauses.append(
            "The progression is especially visible in " + _human_join(metric_interest[:3])
        )
    if damage_interest:
        clauses.append(
            "there are also signs of " + _human_join(damage_interest[:2])
        )
    if alert_sentence:
        clauses.append(alert_sentence[0].lower() + alert_sentence[1:])

    if not clauses:
        return ""
    return ". ".join(clause.rstrip(".") for clause in clauses) + "."


def _build_latest_state_sentence(
    component_id: str,
    status: str,
    latest_timestamp: str | None,
    prediction: dict[str, Any] | None,
) -> str:
    component_name = component_id.replace("_", " ")
    if status == "FAILED":
        sentence = f"By the most recent record, {component_name} had already moved into a failed condition"
    elif status == "CRITICAL":
        sentence = f"In the latest record, {component_name} is already in a critical condition"
    elif status == "DEGRADED":
        sentence = f"The latest record places {component_name} in a degraded condition"
    else:
        sentence = f"In the latest record, {component_name} remains in its current monitored state"

    if latest_timestamp:
        sentence += f" at {latest_timestamp}"
    sentence += "."
    return sentence


def _build_prediction_sentence(status: str) -> str:
    if status == "FAILED":
        return "The prediction context is consistent with the severity already reached by the component."
    if status == "CRITICAL":
        return "The prediction context suggests there is little remaining margin if the same conditions continue."
    if status == "DEGRADED":
        return "The prediction context suggests the current trend could continue if operating conditions remain unchanged."
    return "The prediction context suggests this behavior should still be monitored under similar conditions."


def _human_join(items: list[str]) -> str:
    filtered = [item for item in items if item]
    if not filtered:
        return ""
    if len(filtered) == 1:
        return filtered[0]
    if len(filtered) == 2:
        return f"{filtered[0]} and {filtered[1]}"
    return ", ".join(filtered[:-1]) + f", and {filtered[-1]}"
