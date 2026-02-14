import { getToken, clearToken } from './auth'

// Configure in .env.local as VITE_API_BASE=http://localhost:8000
export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ??
  import.meta.env.VITE_API_BASE ??
  'http://localhost:8000'

export class ApiError extends Error {
  status?: number
  url?: string
  reason?: string

  constructor(message: string, status?: number, url?: string, reason?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.url = url
    this.reason = reason
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
    let reason: string | undefined
    try {
      const data = await res.json()
      const detail = data?.detail
      if (typeof detail === 'string') {
        msg = detail
      } else if (detail && typeof detail === 'object') {
        reason = String((detail as { reason?: string }).reason ?? '') || undefined
        msg = String((detail as { message?: string }).message ?? reason ?? JSON.stringify(detail))
      } else {
        msg = JSON.stringify(data)
      }
    } catch {
      // ignore
    }
    throw new ApiError(msg, res.status, url, reason)
  }
  return (await res.json()) as T
}
