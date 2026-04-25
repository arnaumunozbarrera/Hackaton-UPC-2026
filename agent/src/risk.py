def compute_risk_score(projected_health: float, predicted_status: str, cost: float = 0.0) -> float:
    status_penalty = {
        "FAILED": 200.0,
        "CRITICAL": 100.0,
        "DEGRADED": 30.0,
        "FUNCTIONAL": 0.0,
        "UNKNOWN": 50.0,
    }

    health_penalty = (1.0 - projected_health) * 100.0

    return round(status_penalty[predicted_status] + health_penalty + cost, 4)