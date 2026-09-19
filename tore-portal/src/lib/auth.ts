import { clearAllIncidentDrafts } from './incidentDraft'
const TOKEN_KEY = 'tore_partner_token'
const SESSION_KEY = 'tore_partner_session'

export type PartnerSession = {
  bar_id: number
  display_name: string
  role?: string
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(SESSION_KEY)
  clearAllIncidentDrafts()
}

export function getSession(): PartnerSession | null {
  const raw = localStorage.getItem(SESSION_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as PartnerSession
  } catch {
    return null
  }
}

export function setSession(session: PartnerSession) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session))
}
