"""Helpers for persisting and loading offline-trained AI predictor artifacts."""

from __future__ import annotations

import pickle
from datetime import datetime, timezone
from pathlib import Path


ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"


def _artifact_path(component_id: str) -> Path:
    return ARTIFACTS_DIR / f"{component_id}.pkl"


def list_expected_artifact_paths(component_ids: list[str]) -> list[Path]:
    return [_artifact_path(component_id) for component_id in component_ids]


def save_model_artifact(
    component_id: str,
    model,
    training: dict,
    model_family: str,
    prediction_method: str,
) -> dict:
    """Persist an offline-trained model artifact for later inference."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    artifact = {
        "component_id": component_id,
        "model_family": model_family,
        "prediction_method": prediction_method,
        "saved_at": (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        ),
        "training": dict(training),
        "model": model,
    }
    with _artifact_path(component_id).open("wb") as artifact_file:
        pickle.dump(artifact, artifact_file)
    return artifact


def load_model_artifact(component_id: str) -> dict:
    """Load a persisted model artifact for inference."""
    artifact_path = _artifact_path(component_id)
    if not artifact_path.exists():
        raise FileNotFoundError(
            f"AI model artifact not found for component_id={component_id}. "
            f"Run offline training to generate {artifact_path}."
        )
    with artifact_path.open("rb") as artifact_file:
        return pickle.load(artifact_file)


def artifact_exists(component_id: str) -> bool:
    return _artifact_path(component_id).exists()
