from agent.src.schemas import Forecast


def forecast_from_health_trend(history: list[dict], component_id: str, horizon_steps: int) -> Forecast:
    if len(history) < 2:
        return Forecast(
            horizon_steps=horizon_steps,
            predicted_status="UNKNOWN",
            time_to_critical_steps=None,
            time_to_failure_steps=None,
            risk_score=0.0,
        )

    first = history[0]["components"][component_id]["health_index"]
    last = history[-1]["components"][component_id]["health_index"]
    steps = len(history) - 1
    degradation_rate = max((first - last) / steps, 0.0)

    if degradation_rate == 0.0:
        return Forecast(
            horizon_steps=horizon_steps,
            predicted_status=history[-1]["components"][component_id]["status"],
            time_to_critical_steps=None,
            time_to_failure_steps=None,
            risk_score=(1.0 - last) * 10.0,
        )

    critical_threshold = 0.30
    failure_threshold = 0.05

    time_to_critical = int((last - critical_threshold) / degradation_rate) if last > critical_threshold else 0
    time_to_failure = int((last - failure_threshold) / degradation_rate) if last > failure_threshold else 0

    future_health = max(0.0, last - degradation_rate * horizon_steps)

    if future_health <= failure_threshold:
        predicted_status = "FAILED"
    elif future_health <= critical_threshold:
        predicted_status = "CRITICAL"
    elif future_health <= 0.70:
        predicted_status = "DEGRADED"
    else:
        predicted_status = "FUNCTIONAL"

    risk_score = (1.0 - future_health) * 100.0

    return Forecast(
        horizon_steps=horizon_steps,
        predicted_status=predicted_status,
        time_to_critical_steps=max(time_to_critical, 0),
        time_to_failure_steps=max(time_to_failure, 0),
        risk_score=risk_score,
    )