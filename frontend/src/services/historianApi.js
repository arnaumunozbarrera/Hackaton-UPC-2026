import { fetchJson } from './apiClient';

export async function listRuns() {
  return fetchJson('/api/historian/runs');
}

export async function getRunTimeline(runId) {
  return fetchJson(`/api/historian/runs/${runId}/timeline`);
}
