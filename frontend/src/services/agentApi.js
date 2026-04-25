import { fetchJson } from './apiClient';

const DEFAULT_LLM_QUESTION = 'Why do you recommend this maintenance plan?';

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
