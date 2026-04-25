FAILED_HEALTH_THRESHOLD = 0.15
CRITICAL_HEALTH_THRESHOLD = 0.40
DEGRADED_HEALTH_THRESHOLD = 0.70


def status_from_health(health: float) -> str:
    if health < FAILED_HEALTH_THRESHOLD:
        return "FAILED"
    if health < CRITICAL_HEALTH_THRESHOLD:
        return "CRITICAL"
    if health < DEGRADED_HEALTH_THRESHOLD:
        return "DEGRADED"
    return "FUNCTIONAL"


def severity_from_health(health: float) -> str:
    if health < FAILED_HEALTH_THRESHOLD:
        return "FAILED"
    if health < CRITICAL_HEALTH_THRESHOLD:
        return "CRITICAL"
    if health < DEGRADED_HEALTH_THRESHOLD:
        return "WARNING"
    return "INFO"