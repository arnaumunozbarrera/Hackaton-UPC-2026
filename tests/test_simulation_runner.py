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


def _component_health_timeline(result: dict, component_id: str) -> list[float]:
    return [
        point["model_output"]["components"][component_id]["health"]
        for point in result["timeline"]
    ]


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


def test_stochasticity_materially_changes_health_curve():
    deterministic_result = run_simulation(
        _config("deterministic_curve", total_usages=240, usage_step=4, stochasticity=0.0)
    )
    stochastic_result = run_simulation(
        _config("stochastic_curve", total_usages=240, usage_step=4, stochasticity=1.0)
    )

    deterministic_health = _component_health_timeline(
        deterministic_result,
        "heating_elements",
    )
    stochastic_health = _component_health_timeline(
        stochastic_result,
        "heating_elements",
    )
    deterministic_drops = [
        deterministic_health[index - 1] - deterministic_health[index]
        for index in range(1, len(deterministic_health))
    ]
    stochastic_drops = [
        stochastic_health[index - 1] - stochastic_health[index]
        for index in range(1, len(stochastic_health))
    ]

    max_curve_difference = max(
        abs(deterministic - stochastic)
        for deterministic, stochastic in zip(deterministic_health, stochastic_health)
    )

    assert max_curve_difference > 0.02
    assert max(stochastic_drops) - min(stochastic_drops) > 0.004
    assert max(stochastic_drops) - min(stochastic_drops) > 4 * (
        max(deterministic_drops) - min(deterministic_drops)
    )


def test_stochasticity_is_reproducible_for_same_seed():
    first_result = run_simulation(
        _config("seeded_curve_a", total_usages=120, usage_step=4, stochasticity=1.0)
    )
    second_result = run_simulation(
        _config("seeded_curve_b", total_usages=120, usage_step=4, stochasticity=1.0)
    )

    first_health = _component_health_timeline(first_result, "heating_elements")
    second_health = _component_health_timeline(second_result, "heating_elements")
    first_drivers = [point["drivers"] for point in first_result["timeline"]]
    second_drivers = [point["drivers"] for point in second_result["timeline"]]

    assert second_health == first_health
    assert second_drivers == first_drivers


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
