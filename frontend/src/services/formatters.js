export function formatLabel(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function formatMetricValue(value) {
  if (typeof value !== 'number') return value;
  if (Math.abs(value) >= 100) return value.toFixed(1);
  if (Math.abs(value) >= 10) return value.toFixed(2);
  if (Math.abs(value) >= 1) return value.toFixed(3);
  return value.toFixed(4);
}

export function getStatusFromHealth(health) {
  if (health <= 0.15) return 'FAILED';
  if (health <= 0.4) return 'CRITICAL';
  if (health <= 0.7) return 'DEGRADED';
  return 'FUNCTIONAL';
}

export function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}
