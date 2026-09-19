const TOKEN_KEY = 'tore_partner_token'
const SESSION_KEY = 'tore_partner_session'

export type PartnerSession = {
  bar_id: number
  display_name: string
  role?: string
}

function clearLegacy() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(SESSION_KEY)
}

clearLegacy()

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string) {
  clearLegacy()
  sessionStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(SESSION_KEY)
  clearLegacy()
}

export function getSession(): PartnerSession | null {
  const raw = sessionStorage.getItem(SESSION_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as PartnerSession
  } catch {
    sessionStorage.removeItem(SESSION_KEY)
    return null
  }
}

export function setSession(session: PartnerSession) {
  clearLegacy()
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
}
