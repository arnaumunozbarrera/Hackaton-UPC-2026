from agent.src.decision import make_agent_decisions
from agent.src.llm_context import build_llm_context
from agent.src.response import build_agent_response


COMPONENT_IDS = [
    "recoater_blade",
    "linear_guide",
    "recoater_drive_motor",
    "nozzle_plate",
    "thermal_firing_resistors",
    "cleaning_interface",
    "heating_elements",
    "temperature_sensors",
    "insulation_panels",
]

SUBSYSTEMS = {
    "recoater_blade": "recoating_system",
    "linear_guide": "recoating_system",
    "recoater_drive_motor": "recoating_system",
    "nozzle_plate": "printhead_array",
    "thermal_firing_resistors": "printhead_array",
    "cleaning_interface": "printhead_array",
    "heating_elements": "thermal_control",
    "temperature_sensors": "thermal_control",
    "insulation_panels": "thermal_control",
}


def test_agent_llm_context_covers_all_degraded_components():
    history = [
        _record(step_index=0, health_index=0.82),
        _record(step_index=1, health_index=0.72),
        _record(step_index=2, health_index=0.62),
    ]

    decisions = make_agent_decisions(
        run_id="all-components-run",
        latest_record=history[-1],
        history=history,
        horizon_steps=6,
    )
    analysis = build_agent_response("all-components-run", decisions)
    context = build_llm_context(
        run_id="all-components-run",
        question="What should we do?",
        analysis=analysis,
    )

    decision_components = {decision.diagnosis.component_id for decision in decisions}
    required_components = set(context["analysis_summary"]["required_components"])

    assert decision_components == set(COMPONENT_IDS)
    assert required_components == set(COMPONENT_IDS)
    assert context["analysis_summary"]["decision_count"] == len(COMPONENT_IDS)


def _record(step_index: int, health_index: float) -> dict:
    return {
        "run_id": "all-components-run",
        "scenario_id": "all-components",
        "step_index": step_index,
        "usage_count": float(step_index),
        "timestamp": f"2026-04-25T00:0{step_index}:00Z",
        "drivers": {
            "operational_load": 0.8,
            "contamination": 0.35,
            "humidity": 0.4,
            "temperature_stress": 0.55,
            "maintenance_level": 0.2,
        },
        "components": {
            component_id: _component(component_id, health_index)
            for component_id in COMPONENT_IDS
        },
    }


def _component(component_id: str, health_index: float) -> dict:
    return {
        "component": component_id,
        "subsystem": SUBSYSTEMS[component_id],
        "health_index": health_index,
        "status": "DEGRADED",
        "damage": {"total": round(1.0 - health_index, 4)},
        "metrics": {},
        "alerts": [],
    }
