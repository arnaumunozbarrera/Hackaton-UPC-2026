"""Offline training script for AI component predictors."""

from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
for path in (BACKEND_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.prediction.artifact_store import save_model_artifact
from app.prediction.registry import (
    MODEL_FAMILY_BY_COMPONENT,
    PREDICTION_METHOD,
    TRAINERS_BY_COMPONENT,
)


def train_all_models() -> dict:
    summary = {"artifacts": []}
    for component_id, trainer in TRAINERS_BY_COMPONENT.items():
        model, training = trainer()
        artifact = save_model_artifact(
            component_id=component_id,
            model=model,
            training=training,
            model_family=MODEL_FAMILY_BY_COMPONENT[component_id],
            prediction_method=PREDICTION_METHOD,
        )
        summary["artifacts"].append(
            {
                "component_id": component_id,
                "model_family": artifact["model_family"],
                "saved_at": artifact["saved_at"],
                "training_samples": training["training_samples"],
            }
        )
    return summary


if __name__ == "__main__":
    print(json.dumps(train_all_models(), indent=2))
