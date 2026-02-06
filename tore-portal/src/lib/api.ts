import { getToken, clearToken } from './auth'

// Configure in .env.local as VITE_API_BASE=http://localhost:8000
export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ??
  import.meta.env.VITE_API_BASE ??
  'http://localhost:8000'


export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  } catch {
    throw new Error('API indisponible. Vérifie la connexion.')
  }
  if (res.status === 401) {
    clearToken()
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const data = await res.json()
      msg = data?.detail ? String(data.detail) : JSON.stringify(data)
    } catch {
      // ignore
    }
    throw new Error(msg)
  }
  return (await res.json()) as T
}
