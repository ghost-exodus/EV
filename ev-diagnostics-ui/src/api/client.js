/**
 * API Client — Centralized fetch wrapper with JWT bearer token.
 *
 * - Reads base URL from VITE_API_BASE_URL env var
 * - Attaches Authorization header from localStorage
 * - Returns parsed JSON
 * - Throws ApiError with status code and body for non-2xx responses
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.detail || body?.error || `Request failed with status ${status}`);
    this.status = status;
    this.body = body;
  }
}

/**
 * Core fetch wrapper.
 * @param {string} path - API path (e.g. '/api/v1/fleet/summary')
 * @param {RequestInit} options - fetch options
 * @returns {Promise<any>} Parsed JSON response
 */
export async function apiFetch(path, options = {}) {
  const token = localStorage.getItem('ev_token');

  const headers = {
    ...options.headers,
  };

  // Attach JWT for authenticated endpoints
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Default to JSON content type unless it's form data
  if (!options.isFormData && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: options.isFormData
      ? { ...headers, 'Content-Type': undefined } // Let browser set for form data
      : headers,
  });

  // Parse response
  let body;
  const contentType = res.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    body = await res.json();
  } else {
    body = await res.text();
  }

  if (!res.ok) {
    throw new ApiError(res.status, body);
  }

  return body;
}

/**
 * POST /auth/token — OAuth2 password grant (form-urlencoded).
 * @param {string} username
 * @param {string} password
 * @returns {Promise<{access_token: string, token_type: string, role: string}>}
 */
export async function loginApi(username, password) {
  const formBody = new URLSearchParams();
  formBody.append('username', username);
  formBody.append('password', password);

  const res = await fetch(`${BASE_URL}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: formBody.toString(),
  });

  const body = await res.json();

  if (!res.ok) {
    throw new ApiError(res.status, body);
  }

  return body;
}

// ── Convenience helpers for each endpoint ─────────────────────────────────────

export const getFleetSummary = () => apiFetch('/api/v1/fleet/summary');

export const getTelemetry = (batteryId, limit = 100, cursor = null) => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) params.set('cursor', cursor);
  return apiFetch(`/api/v1/telemetry/${batteryId}?${params}`);
};

export const getSoH = (batteryId) => apiFetch(`/api/v1/soh/${batteryId}`);

export const getRUL = (batteryId) => apiFetch(`/api/v1/rul/${batteryId}`);

export const getDegradation = (batteryId, startDate, endDate) => {
  const params = new URLSearchParams({ battery_id: batteryId });
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  return apiFetch(`/api/v1/analytics/degradation?${params}`);
};

export const getHealth = () => apiFetch('/health');
