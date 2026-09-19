import { clearToken, getToken, setToken } from './auth';

export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://127.0.0.1:8001' : '')).toString().replace(/\/+$/, '');

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) { super(message); this.name = 'ApiError'; this.status = status; }
}

function webHeaders(headers?: HeadersInit): Headers {
  const out = new Headers(headers);
  out.set('X-TORE-Web', '1');
  return out;
}

export async function refreshWebSession(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/auth/web/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: webHeaders(),
    });
    if (!response.ok) return false;
    const data = (await response.json()) as { access_token?: string };
    if (!data.access_token) return false;
    setToken(data.access_token);
    return true;
  } catch {
    return false;
  }
}

export async function webLogout(): Promise<void> {
  const token = getToken();
  const headers = webHeaders();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(`${API_BASE}/auth/web/logout`, {
    method: 'POST',
    credentials: 'include',
    headers,
  });
  if (!response.ok) {
    throw new ApiError(`Logout failed (HTTP ${response.status})`, response.status);
  }
  clearToken();
}

async function request(path: string, init: RequestInit, token: string | null): Promise<Response> {
  const headers = new Headers(init.headers);
  const isFormData = typeof FormData !== 'undefined' && init.body instanceof FormData;
  if (!headers.has('Content-Type') && init.body && !isFormData) headers.set('Content-Type', 'application/json');
  if (path.startsWith('/auth/web/')) headers.set('X-TORE-Web', '1');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return fetch(`${API_BASE}${path}`, { ...init, credentials: 'include', headers });
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const initialToken = getToken();
  let activeToken = initialToken;
  let res = await request(path, init, activeToken);

  if (res.status === 401 && !path.startsWith('/auth/web/') && getToken() === initialToken) {
    if (await refreshWebSession()) {
      activeToken = getToken();
      res = await request(path, init, activeToken);
    }
  }

  if (res.status === 401 && activeToken && getToken() === activeToken) clearToken();
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (typeof data.detail === 'string') message = data.detail;
      else if (data.detail && typeof data.detail === 'object') message = JSON.stringify(data.detail);
    } catch { /* ignore parse error */ }
    throw new ApiError(message, res.status);
  }
  if (res.status === 204 || res.status === 205) return undefined as T;
  return (await res.json()) as T;
}
