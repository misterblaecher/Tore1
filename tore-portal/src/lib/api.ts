import { getToken, clearToken } from './auth'

// Configure in .env.local as VITE_API_BASE_URL=http://localhost:8000
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
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export async function logoutPartnerSession(): Promise<void> {
  const token = getToken()
  try {
    if (token) {
      await fetch(`${API_BASE}/partner/auth/revoke-token`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
    }
  } finally {
    clearToken()
  }
}

export async function apiText(path: string, init: RequestInit = {}): Promise<string> {
  const token = getToken()
  const headers = new Headers(init.headers)
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

  return res.text()
}


type ShortlinkKind = 'event_share' | 'orga_share' | 'open_url'

type ShortlinkParams = {
  kind: ShortlinkKind
  event_id?: number
  orga_id?: number
  open_type?: string
  open_id?: number
  open_code?: string
  expiresInSeconds?: number
}

export async function createShortlink(params: ShortlinkParams): Promise<{ shortUrl: string; openUrl: string; fallbackOpenUrl?: string; expiresAt?: string; slug: string } | null> {
  try {
    const idem = `short-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    return await api('/shortlinks', {
      method: 'POST',
      headers: { 'Idempotency-Key': idem },
      body: JSON.stringify(params),
    })
  } catch {
    return null
  }
}


export async function adminApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  const res = await fetch(`/admin-api${path}`, { ...init, headers })
  if (!res.ok) {
    throw new ApiError(`HTTP ${res.status}`, res.status, `/admin-api${path}`)
  }
  return (await res.json()) as T
}
