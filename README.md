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

## Results

The current result is a functional prototype that connects subsystem modeling with a visualization layer for monitoring component condition and maintenance-related indicators.

The platform is intended to display:

- The health state and degradation evolution of each implemented subsystem.
- Alerts and interpretable indicators that support maintenance decisions.
- One timeline for each type of implemented subsystem, so the evolution of every subsystem can be analyzed independently over time.

## Future Improvements

Two complementary improvement approaches are considered:

1. Add more data to the model.
   This includes incorporating more constant and component-specific parameters such as humidity, degradation rate, and other operational variables that affect wear and failure behavior.

2. Focus the solution on warning generation and maintenance date estimation.
   The goal is to implement a system more centered on early warnings and on estimating the date when maintenance should be performed. This would optimize two related fields: demand and maintenance waiting time. As a result, the system could reduce costs by lowering machine unavailability and minimizing unnecessary maintenance impact.
