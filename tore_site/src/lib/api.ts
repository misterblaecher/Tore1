import { clearToken, getToken } from './auth';

export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://127.0.0.1:8001' : '')).toString().replace(/\/+$/, '');

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) { super(message); this.name = 'ApiError'; this.status = status; }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const isFormData = typeof FormData !== 'undefined' && init.body instanceof FormData;
  if (!headers.has('Content-Type') && init.body && !isFormData) headers.set('Content-Type', 'application/json');
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (res.status === 401 && token && getToken() === token) clearToken();
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try { const data = (await res.json()) as { detail?: unknown }; if (typeof data.detail === 'string') message = data.detail; else if (data.detail && typeof data.detail === 'object') message = JSON.stringify(data.detail); } catch { /* ignore parse error */ }
    throw new ApiError(message, res.status);
  }
  if (res.status === 204 || res.status === 205) return undefined as T;
  return (await res.json()) as T;
}
