const TOKEN_KEY = 'tore_partner_token'
const SESSION_KEY = 'tore_partner_session'

export type PartnerSession = {
  bar_id: number
  display_name: string
  role?: string
}

function migrateLegacy(key: string): string | null {
  try {
    const current = sessionStorage.getItem(key)
    if (current) {
      localStorage.removeItem(key)
      return current
    }
    const legacy = localStorage.getItem(key)
    if (!legacy) return null
    sessionStorage.setItem(key, legacy)
    localStorage.removeItem(key)
    return legacy
  } catch {
    return null
  }
}

export function getToken(): string | null {
  return migrateLegacy(TOKEN_KEY)
}

export function setToken(token: string) {
  localStorage.removeItem(TOKEN_KEY)
  sessionStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(SESSION_KEY)
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(SESSION_KEY)
}

export function getSession(): PartnerSession | null {
  const raw = migrateLegacy(SESSION_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as PartnerSession
  } catch {
    sessionStorage.removeItem(SESSION_KEY)
    localStorage.removeItem(SESSION_KEY)
    return null
  }
}

export function setSession(session: PartnerSession) {
  localStorage.removeItem(SESSION_KEY)
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
}
