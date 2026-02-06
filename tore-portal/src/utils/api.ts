import { getToken } from './auth'

const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? 'http://localhost:8000'

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    let detail: any = null
    try {
      detail = await res.json()
    } catch {
      // ignore
    }
    const msg = detail?.detail ?? `HTTP ${res.status}`
    throw new Error(msg)
  }
  // 204 / empty
  if (res.status === 204) return undefined as any
  return (await res.json()) as T
}
