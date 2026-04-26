import { fetchJson } from './apiClient';

/**
 * Builds placeholder chart points so the usage axis is stable before results arrive.
 *
 * @param {number} totalUsages - Total configured usage count.
 * @param {number} usageStep - Desired spacing between visible usage points.
 * @returns {Array<object>} Placeholder points with null health and status values.
 */
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
