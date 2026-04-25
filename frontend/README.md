# Digital Twin Frontend

React + Vite frontend for the Component Health Index Estimation dashboard.

## What is included

- Dark minimal UI.
- Component selector.
- Runtime stochastic timeline with fixed axes and line construction during execution.
- Placeholder interactive 3D component model with React Three Fiber.
- Human-readable dependency impact panel.
- Mock model contract aligned with the expected Python model output:
  - `machine_state`
  - `components`
  - `health`
  - `status`
  - `damage`
  - `metrics`
  - `alerts`
- Frontend-only SQLite historian using `sql.js` and browser `localStorage`.

## Important packaging note

This repository intentionally does **not** include:

- `node_modules/`
- `dist/`
- `package-lock.json`

The previous generated lock file contained environment-specific internal registry URLs. This corrected version pins stable dependency versions in `package.json` and includes `.npmrc` configured for the public npm registry.

## Install

```bash
cd frontend
npm install
npm run dev
```

## Build

```bash
npm run build
```

## Future Python integration

Replace the placeholder logic in:

```txt
src/services/modelApi.js
src/services/simulationApi.js
src/services/historianApi.js
```

Expected future routes can be shaped like:

```txt
POST /api/model/predict
POST /api/simulation/run
GET  /api/historian/runs/:runId
```
