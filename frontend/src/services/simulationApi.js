import { fetchJson } from './apiClient';

export function buildAxisTemplate(totalUsages, usageStep) {
  const steps = Math.max(1, Math.floor(totalUsages / usageStep));
  return Array.from({ length: steps + 1 }, (_, index) => ({
    usage_count: index * usageStep,
    health: null,
    status: null
  }));
}

export async function runSimulation(config) {
  return fetchJson('/api/simulation/run', {
    method: 'POST',
    body: JSON.stringify(config)
  });
}

export async function runSimulationStep(payload) {
  return fetchJson('/api/simulation/step', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}
