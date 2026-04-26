"""Prediction helpers based on historian timelines."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.storage import historian


FAILED_THRESHOLD = 0.15


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _to_iso8601(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _not_enough_data(run_id: str, component_id: str) -> dict:
    """Build the standard low-confidence prediction response.

    @param run_id: Run identifier requested by the caller.
    @param component_id: Component identifier requested by the caller.
    @return: Prediction response explaining that trend data is insufficient.
    """
    return {
        "run_id": run_id,
        "component_id": component_id,
        "confidence": 0.2,
        "reason": "Not enough historical points to estimate a reliable trend.",
    }


def _normalize_timeline_for_prediction(timeline: list[dict]) -> list[dict]:
    """Normalize API and historian timeline shapes before trend estimation.

    @param timeline: Timeline points from either simulation output or historian storage.
    @return: Timeline points with top-level component maps and health_index fields.
    """
    normalized = []
    for point in timeline:
        if "components" in point:
            normalized.append(point)
            continue

        components = {}
        for component_id, component in point.get("model_output", {}).get("components", {}).items():
            components[component_id] = {
                "health_index": component.get("health", component.get("health_index")),
                "status": component["status"],
                "metrics": component.get("metrics", {}),
                "damage": component.get("damage", {}),
                "alerts": component.get("alerts", []),
            }

        normalized.append(
            {
                "run_id": point.get("run_id"),
                "scenario_id": point.get("scenario_id"),
                "usage_count": point["usage_count"],
                "timestamp": point["timestamp"],
                "drivers": point.get("drivers", {}),
                "components": components,
            }
        )

    return normalized


def predict_component_failure_from_timeline(
    run_id: str,
    component_id: str,
    timeline: list[dict],
) -> dict:
    """Estimate component failure from a simple observed health trend.

    @param run_id: Run identifier associated with the timeline.
    @param component_id: Component whose health trend should be projected.
    @param timeline: Historical timeline records containing component health values.
    @return: Prediction payload with failure estimate, confidence, and supporting evidence.
    """
    timeline = [
        point
        for point in _normalize_timeline_for_prediction(timeline)
        if component_id in point.get("components", {})
    ]

    if len(timeline) < 2:
        return _not_enough_data(run_id, component_id)

    points = []
    for point in timeline:
        component = point["components"].get(component_id)
        if component is None:
            continue
        points.append(
            {
                "usage_count": float(point["usage_count"]),
                "timestamp": point["timestamp"],
                "health_index": float(component["health_index"]),
                "status": component["status"],
            }
        )

    if len(points) < 2:
        return _not_enough_data(run_id, component_id)

    first_point = points[0]
    last_point = points[-1]
    delta_usage = last_point["usage_count"] - first_point["usage_count"]
    delta_health = first_point["health_index"] - last_point["health_index"]

    if delta_usage <= 0 or delta_health <= 0:
        return _not_enough_data(run_id, component_id)

    slope = delta_health / delta_usage
    current_health = last_point["health_index"]
    current_usage = last_point["usage_count"]
    usages_until_failure = max((current_health - FAILED_THRESHOLD) / slope, 0.0)
    predicted_failure_usage = round(current_usage + usages_until_failure, 2)
    last_timestamp = _parse_timestamp(last_point["timestamp"])
    predicted_failure_timestamp = _to_iso8601(last_timestamp + timedelta(minutes=usages_until_failure))

    confidence = max(0.2, min(0.92, 0.45 + min(delta_usage / 96.0, 0.3) + min(delta_health * 0.8, 0.17)))

    return {
        "run_id": run_id,
        "component_id": component_id,
        "predicted_failure_timestamp": predicted_failure_timestamp,
        "predicted_failure_usage": predicted_failure_usage,
        "confidence": round(confidence, 2),
        "evidence": {
            "run_id": run_id,
            "timestamp": last_point["timestamp"],
            "usage_count": current_usage,
            "health": current_health,
            "status": last_point["status"],
        },
    }


def predict_component_failure(run_id: str, component_id: str) -> dict:
    return predict_component_failure_from_timeline(
        run_id,
        component_id,
        historian.get_component_history(run_id, component_id),
    )
