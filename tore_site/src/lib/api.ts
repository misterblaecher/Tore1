import { clearToken, getToken, setToken } from './auth';

export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://127.0.0.1:8001' : '')).toString().replace(/\/+$/, '');

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) { super(message); this.name = 'ApiError'; this.status = status; }
}

let refreshPromise: Promise<string | null> | null = null;

async function responseError(res: Response): Promise<ApiError> {
  let message = `HTTP ${res.status}`;
  try {
    const data = (await res.json()) as { detail?: unknown };
    if (typeof data.detail === 'string') message = data.detail;
    else if (data.detail && typeof data.detail === 'object') message = JSON.stringify(data.detail);
  } catch { /* ignore parse error */ }
  return new ApiError(message, res.status);
}

export async function refreshWebSession(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/web/refresh`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!res.ok) {
        clearToken();
        return null;
      }
      const data = (await res.json()) as { access_token?: string; token?: string };
      const accessToken = data.access_token ?? data.token ?? null;
      if (!accessToken) {
        clearToken();
        return null;
      }
      setToken(accessToken);
      return accessToken;
    } catch {
      return null;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

export async function logoutWebSession(): Promise<void> {
  const token = getToken();
  try {
    await fetch(`${API_BASE}/auth/web/logout`, {
      method: 'POST',
      credentials: 'include',
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
  } finally {
    clearToken();
  }
}

async function performFetch(path: string, init: RequestInit, token: string | null): Promise<Response> {
  const headers = new Headers(init.headers);
  const isFormData = typeof FormData !== 'undefined' && init.body instanceof FormData;
  if (!headers.has('Content-Type') && init.body && !isFormData) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: init.credentials ?? (path.startsWith('/auth/web/') ? 'include' : 'same-origin'),
  });
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  let res = await performFetch(path, init, token);

  if (
    res.status === 401 &&
    token &&
    getToken() === token &&
    !path.startsWith('/auth/web/')
  ) {
    const refreshed = await refreshWebSession();
    if (refreshed) res = await performFetch(path, init, refreshed);
  }

  if (res.status === 401 && token && getToken() === token) clearToken();
  if (!res.ok) throw await responseError(res);
  if (res.status === 204 || res.status === 205) return undefined as T;
  return (await res.json()) as T;
}
