# Hackaton-UPC-2026

This repository contains a predictive maintenance and digital twin prototype focused on subsystem health estimation, simulation, and decision support for maintenance planning.

## Architecture

The solution is organized as a modular system with a clear separation between simulation, prediction, orchestration, and visualization:

- `frontend/`: React + Vite dashboard for visualizing component health, alerts, dependencies, and simulation timelines.
- `backend/`: application layer exposing the core prediction, simulation, storage, and chatbot/agent-facing services.
- `agent/`: agent logic and scripts used to support interaction, orchestration, and scenario handling.
- `model_mathematic/`: mathematical models for each subsystem and component degradation behavior.
- `data/`: synthetic histories, example contexts, and agent scenarios used to test the system.
- `docs/`, `config/`, `tests/`, and `3d-models/`: supporting material, configuration, validation, and visualization assets.

At a high level, the mathematical models generate the health and degradation behavior of each subsystem, the backend coordinates predictions and storage, and the frontend presents the results through dashboards and timelines.

## Elements

The main implemented elements of the project are:

- Subsystem-level mathematical models for components such as cleaning interface, heating elements, insulation panels, linear guide, nozzle plate, recoater blade, recoater drive motor, temperature sensors, and thermal firing resistors.
- A logic engine to combine subsystem behavior into machine-level health interpretation.
- A backend structure for prediction, simulation, schema definition, storage, and agent/chatbot integration.
- A frontend dashboard with component selection, health visualization, alerts, dependency impact display, and timeline-based monitoring.
- Synthetic data and agent scenarios to validate the behavior of the platform under different maintenance situations.

## Results & Conclusion

The implemented prediction layer combines several degradation functions depending on the physical behavior of each component family:

- Linear degradation for components whose wear grows approximately in proportion to use and environmental stress.
- Exponential decay for thermal and electrical components whose degradation accelerates with accumulated operating stress.
- Weibull-based degradation for components with fatigue behavior and increasing failure risk over time.

### Linear Prediction Function

The linear formulation is used for components such as the recoater blade, linear guide, cleaning interface, temperature sensors, and insulation panels.

![Linear prediction function](docs/lineal.jpeg)

### Exponential Prediction Function

The exponential formulation is used for components such as heating elements and thermal firing resistors, where damage compounds under repeated thermal and electrical cycles.

![Exponential prediction function](docs/exp.jpeg)

### Weibull Prediction Function

The Weibull formulation is used for the recoater drive motor to represent fatigue accumulation and a non-linear increase in failure probability as effective age grows.

![Weibull prediction function](docs/weibull.jpeg)

### Conclusion

The current prototype delivers a coherent set of prediction functions that are traceable, deterministic, and aligned with the physical interpretation of each subsystem. The main value of the model is not a single universal degradation curve, but the use of the most suitable mathematical behavior for each component type so the digital twin can explain why degradation happens, how it evolves, and when maintenance risk starts to become relevant.

## Future Improvements

Two complementary improvement approaches are considered:

1. Add more data to the model.
   This includes incorporating more constant and component-specific parameters such as humidity, degradation rate, temperature exposure, contamination patterns, maintenance history, and other operational variables that affect wear and failure behavior.

   The utility of this improvement is that the model would stop relying on a relatively compact synthetic description of machine usage and would start representing a richer operational context. In practice, this would allow the digital twin to:

   - Distinguish better between components that fail for similar reasons but under different operating regimes.
   - Capture slower effects such as cumulative environmental exposure, seasonal conditions, or long-term maintenance quality.
   - Reduce oversimplified assumptions in the degradation curves by conditioning them on more realistic combinations of stress factors.
   - Improve the quality of both simulation and prediction outputs, because the backend could generate more nuanced health trajectories instead of a limited number of standard patterns.

   In a more advanced version, this could also support better calibration with real telemetry if production data becomes available, making the model progressively less synthetic and more representative of machine behavior in the field.

2. Focus the solution on warning generation and maintenance date estimation.
   The goal is to implement a system more centered on early warnings and on estimating the date when maintenance should be performed.

   The utility of this improvement is mainly operational. Instead of using the model only to observe degradation, the platform would become a more actionable decision-support tool. This would make it possible to:

   - Trigger interpretable alerts before a component reaches a critical state, giving operators time to react.
   - Estimate when a maintenance intervention should ideally be scheduled, balancing failure risk against unnecessary early replacement.
   - Coordinate maintenance windows with production demand, reducing disruption to machine availability.
   - Prioritize interventions across components and subsystems according to risk, urgency, and expected operational impact.
   - Support cost reduction by avoiding both unplanned downtime and excessive preventive maintenance.

   In business terms, this would make the system more useful for planning, not only for monitoring. The final value would come from converting health predictions into concrete recommendations: when to intervene, why that intervention is needed, and what operational risk is avoided by acting at that moment.
