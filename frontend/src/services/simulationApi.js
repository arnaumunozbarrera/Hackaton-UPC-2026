import { fetchJson } from './apiClient';

export function buildAxisTemplate(totalUsages, usageStep) {
  const usageCounts = [0];
  const epsilon = 1e-9;
  let currentUsage = usageStep;

  while (currentUsage < totalUsages - epsilon) {
    usageCounts.push(Number(currentUsage.toFixed(6)));
    currentUsage += usageStep;
  }

  if (Math.abs(usageCounts[usageCounts.length - 1] - totalUsages) > epsilon) {
    usageCounts.push(Number(totalUsages.toFixed(6)));
  }

  return usageCounts.map((usage_count) => ({
    usage_count,
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
