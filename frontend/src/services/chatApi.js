import { fetchJson } from './apiClient';

export async function sendChatQuery({ question, runId, componentId }) {
  return fetchJson('/api/chat/query', {
    method: 'POST',
    body: JSON.stringify({
      question,
      run_id: runId || null,
      component_id: componentId || null
    })
  });
}
