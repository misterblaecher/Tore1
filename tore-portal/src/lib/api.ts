import { getToken, clearToken } from './auth'

// Configure in .env.local as VITE_API_BASE=http://localhost:8000
export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ??
  import.meta.env.VITE_API_BASE ??
  'http://localhost:8000'

export class ApiError extends Error {
  status?: number
  url?: string

  constructor(message: string, status?: number, url?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.url = url
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let res: Response
  const url = `${API_BASE}${path}`
  try {
    res = await fetch(url, { ...init, headers })
  } catch {
    throw new ApiError('API indisponible. Vérifie la connexion.', undefined, url)
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
    throw new ApiError(msg, res.status, url)
  }
  return (await res.json()) as T
}
