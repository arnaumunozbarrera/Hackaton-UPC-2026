import { fetchJson } from './apiClient';

const DEFAULT_LLM_QUESTION = 'Why do you recommend this maintenance plan?';

/**
 * Requests an agent-backed LLM explanation for a stored simulation run.
 *
 * @param {string} runId - Historian run identifier.
 * @param {object} options - Optional question, horizon, history, and alternative limits.
 * @returns {Promise<object>} LLM answer payload from the backend.
 */
export async function fetchAgentLlmAnswer(runId, options = {}) {
  const provider = import.meta.env.VITE_AGENT_LLM_PROVIDER || 'ollama';
  const model = import.meta.env.VITE_AGENT_LLM_MODEL || null;
  const mode = import.meta.env.VITE_AGENT_LLM_MODE || 'rewrite';

  return fetchJson(`/api/agent/runs/${runId}/llm-answer`, {
    method: 'POST',
    body: JSON.stringify({
      question: options.question || DEFAULT_LLM_QUESTION,
      horizon_steps: options.horizonSteps || 24,
      history_window_steps: options.historyWindowSteps ?? null,
      max_alternatives_per_decision: options.maxAlternativesPerDecision || 5,
      include_context: false,
      provider,
      model,
      mode
    })
  });
}
