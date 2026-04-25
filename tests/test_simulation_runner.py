from datetime import datetime

import pytest

from app.simulation.simulation_runner import run_simulation
from app.storage import historian


@pytest.fixture(autouse=True)
def isolated_historian(tmp_path, monkeypatch):
    monkeypatch.setattr(historian, "DB_PATH", tmp_path / "historian.sqlite")
    historian.initialize_database()


def _config(
    run_id: str,
    total_usages: float,
    usage_step: float,
    stochasticity: float = 0.0,
) -> dict:
    return {
        "run_id": run_id,
        "scenario_id": "simulation_test",
        "total_usages": total_usages,
        "usage_step": usage_step,
        "initial_conditions": {
            "temperature_c": 42,
            "humidity": 0.38,
            "contamination": 0.31,
            "operational_load": 0.72,
            "maintenance_level": 0.64,
            "stochasticity": stochasticity,
        },
        "selected_component": "heating_elements",
        "seed": 1234,
    }


def _health_by_component(result: dict) -> dict:
    return {
        component_id: component["health"]
        for component_id, component in result["timeline"][-1]["model_output"][
            "components"
        ].items()
    }


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_simulation_starts_with_undegraded_initial_snapshot():
    result = run_simulation(_config("initial_snapshot", total_usages=8, usage_step=4))

    first_point = result["timeline"][0]
    second_point = result["timeline"][1]

    assert first_point["usage_count"] == 0.0
    assert first_point["drivers"]["operational_load"] == 0.0
    assert all(
        component["health"] == 1.0
        for component in first_point["model_output"]["components"].values()
    )
    assert any(
        component["health"] < 1.0
        for component in second_point["model_output"]["components"].values()
    )


def test_simulation_degradation_is_independent_of_chart_resolution():
    fine_result = run_simulation(
        _config(
            "fine_resolution",
            total_usages=16,
            usage_step=1,
            stochasticity=0.45,
        )
    )
    coarse_result = run_simulation(
        _config(
            "coarse_resolution",
            total_usages=16,
            usage_step=4,
            stochasticity=0.45,
        )
    )

    fine_health = _health_by_component(fine_result)
    coarse_health = _health_by_component(coarse_result)

    assert coarse_health.keys() == fine_health.keys()
    for component_id in fine_health:
        assert coarse_health[component_id] == pytest.approx(
            fine_health[component_id],
            abs=1e-8,
        )


def test_simulation_records_exact_final_usage_count_when_step_does_not_divide_total():
    result = run_simulation(_config("non_divisible", total_usages=10, usage_step=4))

    usage_counts = [point["usage_count"] for point in result["timeline"]]
    persisted_usage_counts = [
        point["usage_count"]
        for point in historian.get_run_timeline("non_divisible")
    ]
    timestamps = [_parse_timestamp(point["timestamp"]) for point in result["timeline"]]

    assert usage_counts == [0.0, 4, 8, 10]
    assert persisted_usage_counts == usage_counts
    assert (timestamps[1] - timestamps[0]).total_seconds() == 4 * 60
    assert (timestamps[-1] - timestamps[0]).total_seconds() == 10 * 60
