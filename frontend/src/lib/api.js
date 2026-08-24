/**
 * Single entry point for every call to the backend.
 *
 * The API now requires a Bearer token on all /api routes except /api/auth/login.
 * Calling fetch() directly will get a 401, so all components go through here:
 * it attaches the stored token, and turns an expired or revoked session into a
 * clean logout instead of a silent empty screen.
 */

const TOKEN_KEY = 'datalink_token';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem('datalink_user', JSON.stringify(user));
  localStorage.setItem('datalink_auth', 'authenticated');
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem('datalink_user');
  localStorage.removeItem('datalink_auth');
}

/**
 * Broadcast so App can drop back to the lock screen from anywhere, including
 * inside a polling loop in a component that has no access to auth state.
 */
function forceLogout() {
  clearSession();
  window.dispatchEvent(new CustomEvent('datalink:unauthorized'));
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed with status ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

/**
 * fetch() wrapper that injects auth. Same signature and same Response object,
 * so existing `res.ok` / `res.json()` call sites keep working unchanged.
 */
export async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = new Headers(options.headers || {});

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  // Only set JSON content-type when the caller passes a plain string body.
  // FormData must keep the browser-generated multipart boundary.
  if (options.body && typeof options.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const res = await fetch(path, { ...options, headers });

  if (res.status === 401) {
    forceLogout();
  }
  return res;
}

/** apiFetch that parses JSON and throws ApiError on a non-2xx response. */
export async function apiJson(path, options = {}) {
  const res = await apiFetch(path, options);
  if (!res.ok) {
    let detail;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = await res.text().catch(() => '');
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}
