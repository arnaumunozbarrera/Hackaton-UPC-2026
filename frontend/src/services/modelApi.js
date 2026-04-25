import { fetchJson } from './apiClient';

export async function fetchCurrentModel() {
  return fetchJson('/api/model/current');
}

export async function fetchPrediction(runId, componentId) {
  return fetchJson('/api/prediction/component', {
    method: 'POST',
    body: JSON.stringify({
      run_id: runId,
      component_id: componentId
    })
  });
}
