import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
for path in (BACKEND_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.prediction.artifact_store import (
    artifact_exists,
    load_model_artifact,
    save_model_artifact,
)
from app.prediction.registry import (
    MODEL_FAMILY_BY_COMPONENT,
    PREDICTION_METHOD,
    TRAINERS_BY_COMPONENT,
)


@pytest.fixture(scope="session", autouse=True)
def ensure_ai_artifacts_exist():
    for component_id, trainer in TRAINERS_BY_COMPONENT.items():
        should_retrain = not artifact_exists(component_id)
        if not should_retrain:
            artifact = load_model_artifact(component_id)
            training = artifact.get("training", {})
            if component_id in {
                "recoater_blade",
                "recoater_drive_motor",
                "nozzle_plate",
            }:
                teacher = training.get("training_teacher", {})
                should_retrain = (
                    teacher.get("type") != "heuristic_hybrid"
                    or training.get("training_target") != "damage_per_step"
                )

        if not should_retrain:
            continue

        model, training = trainer()
        save_model_artifact(
            component_id=component_id,
            model=model,
            training=training,
            model_family=MODEL_FAMILY_BY_COMPONENT[component_id],
            prediction_method=PREDICTION_METHOD,
        )
