import { INITIAL_MODEL_STATE } from '../data/modelState';
import { getStatusFromHealth } from './formatters';

const MODEL_STATE_KEY = 'digital_twin_latest_model_state';

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

export async function fetchLatestModelState() {
  // Future Python integration:
  // const response = await fetch('/api/model/state/latest');
  // return response.json();

  const stored = localStorage.getItem(MODEL_STATE_KEY);
  return stored ? JSON.parse(stored) : deepClone(INITIAL_MODEL_STATE);
}

export async function saveLatestModelState(modelState) {
  localStorage.setItem(MODEL_STATE_KEY, JSON.stringify(modelState));
  return modelState;
}

export async function fetchPrediction(componentId, modelState, latestTimelinePoint) {
  // Future Python integration:
  // const response = await fetch('/api/model/predict', {
  //   method: 'POST',
  //   headers: { 'Content-Type': 'application/json' },
  //   body: JSON.stringify({ component_id: componentId, model_state: modelState, latest_point: latestTimelinePoint })
  // });
  // return response.json();

  const component = modelState.components[componentId];
  const health = latestTimelinePoint?.health ?? component.health;
  const status = getStatusFromHealth(health);
  const hoursToFailure = Math.max(6, Math.round(health * 140));
  const predictedDate = new Date(Date.now() + hoursToFailure * 60 * 60 * 1000).toISOString();

  const measuresByComponent = {
    recoater_blade: [
      'Inspect the blade edge for abrasive scoring.',
      'Reduce contamination before the next long print run.',
      'Schedule blade replacement if health drops below 0.40.'
    ],
    nozzle_plate: [
      'Run a cleaning cycle and verify blocked nozzle percentage.',
      'Check thermal stress history before continuing production.',
      'Reduce contamination and validate binder jetting efficiency.'
    ],
    heating_elements: [
      'Check resistance drift and energy factor trend.',
      'Verify insulation condition if power demand rises.',
      'Avoid aggressive thermal profiles until stability improves.'
    ]
  };

  const dependencyMap = {
    recoater_blade: ['nozzle_plate'],
    nozzle_plate: ['recoater_blade', 'heating_elements'],
    heating_elements: ['nozzle_plate']
  };

  return {
    component_id: componentId,
    predicted_failure_timestamp: predictedDate,
    predicted_status: status,
    confidence: Math.max(0.55, Math.min(0.94, 1 - health * 0.25)),
    recommended_measures: measuresByComponent[componentId],
    affected_dependencies: dependencyMap[componentId],
    evidence: {
      timestamp: latestTimelinePoint?.timestamp || new Date().toISOString(),
      health,
      status,
      source: 'mock_frontend_model_adapter'
    }
  };
}
