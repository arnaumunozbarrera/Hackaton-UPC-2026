const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Fetches JSON from the backend and normalizes transport or API errors.
 *
 * @param {string} path - Backend API path relative to the configured base URL.
 * @param {object} options - Fetch options merged into the request.
 * @returns {Promise<object|null>} Decoded JSON response payload.
 * @throws {Error} When the backend is unreachable or returns a failed response.
 */
export async function fetchJson(path, options = {}) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {})
      },
      ...options
    });
  } catch (error) {
    throw new Error('Simulation failed: backend is not reachable.');
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch (error) {
    payload = null;
  }

  if (!response.ok) {
    const message = payload?.detail?.message || payload?.message || 'Request failed.';
    throw new Error(message);
  }

  return payload;
}
