from agent.src.schemas import ActionType, Diagnosis, Recommendation, Severity


def recommend_action(diagnosis: Diagnosis) -> Recommendation:
    if diagnosis.issue == "thermal_instability":
        return Recommendation(
            action=ActionType.TRIGGER_COOLDOWN,
            priority=Severity.CRITICAL,
            expected_effect="Reduce thermal stress and slow degradation of heating elements",
            evidence=diagnosis.evidence,
        )

    if diagnosis.issue == "nozzle_clogging":
        return Recommendation(
            action=ActionType.RUN_CLEANING_CYCLE,
            priority=Severity.WARNING,
            expected_effect="Reduce clogging ratio and recover jetting efficiency",
            evidence=diagnosis.evidence,
        )

    if diagnosis.issue == "recoater_wear":
        return Recommendation(
            action=ActionType.SCHEDULE_MAINTENANCE,
            priority=Severity.WARNING,
            expected_effect="Prevent increased powder contamination and downstream nozzle clogging",
            evidence=diagnosis.evidence,
        )

    return Recommendation(
        action=ActionType.CONTINUE_OPERATION,
        priority=Severity.INFO,
        expected_effect="No immediate intervention required",
        evidence=diagnosis.evidence,
    )