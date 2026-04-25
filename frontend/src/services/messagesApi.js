import { fetchJson } from './apiClient';

export async function fetchRunMessages(runId) {
  return fetchJson(`/api/messages/${runId}`);
}
