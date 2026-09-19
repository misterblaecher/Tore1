const TOKEN_KEY = 'tore_partner_token'

function clearLegacy() {
  try { localStorage.removeItem(TOKEN_KEY) } catch { /* ignore unavailable storage */ }
}
clearLegacy()

export function setToken(token: string) {
  clearLegacy()
  sessionStorage.setItem(TOKEN_KEY, token)
}

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function clearToken() {
  sessionStorage.removeItem(TOKEN_KEY)
  clearLegacy()
}
