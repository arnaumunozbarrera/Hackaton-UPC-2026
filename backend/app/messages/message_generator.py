"""Runtime message generation grounded in historian data."""

from __future__ import annotations


SEVERITY_ORDER = {
    "INFO": 0,
    "WARNING": 1,
    "CRITICAL": 2,
    "FAILURE": 3,
}
TOP_RUNTIME_MESSAGE_LIMIT = 3


def health_to_severity(health: float) -> str:
    if health < 0.15:
        return "FAILURE"
    if health < 0.40:
        return "CRITICAL"
    if health < 0.70:
        return "WARNING"
    return "INFO"


def _dominant_damage(component: dict) -> tuple[str | None, float]:
    """Select the strongest non-total damage contributor for a component.

    @param component: Component state containing a damage map.
    @return: Damage name and value, or None with zero when no contributor exists.
    """
    damage = component.get("damage", {})
    candidates = [(key, value) for key, value in damage.items() if key != "total"]
    if not candidates:
        return None, 0.0
    return max(candidates, key=lambda item: item[1])


def _point_components(point: dict) -> dict:
    if "components" in point:
        return point["components"]
    return point.get("model_output", {}).get("components", {})


def _component_health(component: dict) -> float:
    if "health_index" in component:
        return float(component["health_index"])
    return float(component.get("health", 1.0))


def _message_rank(message: dict) -> tuple[int, float, float, str]:
    """Rank runtime messages by severity, health impact, usage, and timestamp.

    @param message: Runtime message generated from the timeline.
    @return: Sortable rank tuple where larger values indicate higher priority.
    """
    evidence = message.get("evidence", {})
    health = evidence.get("health")
    health_priority = 0.0 if health is None else 1.0 - float(health)
    usage_count = float(evidence.get("usage_count", 0.0))
    return (
        SEVERITY_ORDER.get(message.get("severity", "INFO"), 0),
        health_priority,
        usage_count,
        message.get("timestamp", ""),
    )


def select_top_messages(
    messages: list[dict],
    limit: int = TOP_RUNTIME_MESSAGE_LIMIT,
) -> list[dict]:
    """Return the highest-impact runtime messages without repeated event spam.

    @param messages: Candidate runtime messages generated for a run.
    @param limit: Maximum number of messages to return.
    @return: Deduplicated messages sorted by operational relevance.
    """
    if limit <= 0:
        return []

    strongest_by_event = {}
    for message in messages:
        event_key = (message.get("component_id"), message.get("title"))
        current = strongest_by_event.get(event_key)
        if current is None or _message_rank(message) > _message_rank(current):
            strongest_by_event[event_key] = message

    return sorted(strongest_by_event.values(), key=_message_rank, reverse=True)[:limit]


def generate_messages(run_id: str, timeline: list[dict]) -> list[dict]:
    """Generate concise runtime messages from component state transitions.

    @param run_id: Simulation run identifier.
    @param timeline: Ordered simulation timeline containing component states.
    @return: Deduplicated and ranked runtime messages for display and storage.
    """
    messages = []
    previous_severity_by_component = {}
    previous_damage_by_component = {}
    previous_health_by_component = {}

    for point in timeline:
        components = _point_components(point)
        critical_components = [
            component_id
            for component_id, component in components.items()
            if component["status"] == "CRITICAL"
        ]
        failed_components = [
            component_id
            for component_id, component in components.items()
            if component["status"] == "FAILED"
        ]
        for component_id, component in components.items():
            health = _component_health(component)
            severity = health_to_severity(health)
            status = component["status"]
            dominant_damage, dominant_value = _dominant_damage(component)
            previous_severity = previous_severity_by_component.get(component_id)
            previous_dominant = previous_damage_by_component.get(component_id)
            previous_health = previous_health_by_component.get(component_id)

            if previous_severity is not None and previous_severity != severity:
                messages.append(
                    {
                        "run_id": run_id,
                        "component_id": component_id,
                        "timestamp": point["timestamp"],
                        "severity": severity,
                        "title": f"{component_id.replace('_', ' ').title()} threshold crossed",
                        "body": f"{component_id.replace('_', ' ').title()} health reached {health:.2f} at usage {point['usage_count']}.",
                        "evidence": {
                            "usage_count": point["usage_count"],
                            "health": health,
                            "status": status,
                            "dominant_damage": dominant_damage,
                        },
                    }
                )

            if previous_dominant and dominant_damage and previous_dominant != dominant_damage:
                messages.append(
                    {
                        "run_id": run_id,
                        "component_id": component_id,
                        "timestamp": point["timestamp"],
                        "severity": severity,
                        "title": f"{component_id.replace('_', ' ').title()} dominant damage changed",
                        "body": f"{dominant_damage.replace('_', ' ')} became the dominant degradation factor at usage {point['usage_count']}.",
                        "evidence": {
                            "usage_count": point["usage_count"],
                            "health": health,
                            "dominant_damage": dominant_damage,
                            "damage_value": dominant_value,
                        },
                    }
                )

            if previous_health is not None and previous_health - health > 0.08:
                messages.append(
                    {
                        "run_id": run_id,
                        "component_id": component_id,
                        "timestamp": point["timestamp"],
                        "severity": max(severity, "WARNING", key=lambda item: SEVERITY_ORDER[item]),
                        "title": f"{component_id.replace('_', ' ').title()} health dropping quickly",
                        "body": f"Health dropped by {previous_health - health:.2f} between consecutive simulation points.",
                        "evidence": {
                            "usage_count": point["usage_count"],
                            "previous_health": previous_health,
                            "health": health,
                        },
                    }
                )

            if component_id in critical_components and severity in {"CRITICAL", "FAILURE"}:
                messages.append(
                    {
                        "run_id": run_id,
                        "component_id": component_id,
                        "timestamp": point["timestamp"],
                        "severity": severity,
                        "title": f"{component_id.replace('_', ' ').title()} is affecting machine criticality",
                        "body": f"{component_id.replace('_', ' ').title()} is listed in the machine critical components at usage {point['usage_count']}.",
                        "evidence": {
                            "usage_count": point["usage_count"],
                            "health": health,
                            "status": status,
                        },
                    }
                )

            if component_id in failed_components:
                messages.append(
                    {
                        "run_id": run_id,
                        "component_id": component_id,
                        "timestamp": point["timestamp"],
                        "severity": "FAILURE",
                        "title": f"{component_id.replace('_', ' ').title()} failed",
                        "body": f"{component_id.replace('_', ' ').title()} reached failure state at usage {point['usage_count']}.",
                        "evidence": {
                            "usage_count": point["usage_count"],
                            "health": health,
                            "status": status,
                        },
                    }
                )

            for alert in component.get("alerts", []):
                messages.append(
                    {
                        "run_id": run_id,
                        "component_id": component_id,
                        "timestamp": point["timestamp"],
                        "severity": alert.get("severity", severity),
                        "title": f"{component_id.replace('_', ' ').title()}: {alert.get('code', 'alert')}",
                        "body": alert.get("message", "Model alert raised."),
                        "evidence": {
                            "usage_count": point["usage_count"],
                            "health": health,
                            "status": status,
                            "alert_code": alert.get("code"),
                        },
                    }
                )

            previous_severity_by_component[component_id] = severity
            previous_damage_by_component[component_id] = dominant_damage
            previous_health_by_component[component_id] = health

    deduplicated = []
    seen = set()
    for message in messages:
        key = (message["component_id"], message["timestamp"], message["title"])
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(message)

    top_messages = select_top_messages(deduplicated)

    return [
        {
            "id": f"msg_{index + 1:03d}",
            **message,
        }
        for index, message in enumerate(top_messages)
    ]
