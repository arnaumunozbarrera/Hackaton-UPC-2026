def compute_risk_score(projected_health: float, predicted_status: str, cost: float = 0.0) -> float:
    """Compute a scalar risk score from health, status, and action cost.

    @param projected_health: Projected component health index.
    @param predicted_status: Projected component status.
    @param cost: Optional operational cost or burden penalty.
    @return: Rounded risk score where higher values indicate higher risk.
    """
    status_penalty = {
        "FAILED": 200.0,
        "CRITICAL": 100.0,
        "DEGRADED": 30.0,
        "FUNCTIONAL": 0.0,
        "UNKNOWN": 50.0,
    }

    health_penalty = (1.0 - projected_health) * 100.0

    return round(status_penalty[predicted_status] + health_penalty + cost, 4)
