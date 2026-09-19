export const ACCESS_TOKEN_KEY = 'tore_site_access_token';
export const REFRESH_TOKEN_KEY = 'tore_site_refresh_token';

export type MeResponse = {
  id: string;
  display_name: string;
  email?: string | null;
  username?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  nickname?: string | null;
  phone?: string | null;
  instagram_handle?: string | null;
  city?: string | null;
  oripeaux?: string | null;
  avatar_url?: string | null;
  address_text?: string | null;
  show_address?: boolean;
  show_avatar?: boolean;
  visibility?: string | null;
  bio?: string | null;
  account_mode?: 'user' | 'organizer' | 'team';
  role_request_pending?: { requested_mode: 'user' | 'organizer' | 'team'; status: string } | null;
};

let meCache: MeResponse | null = null;
let meCacheToken: string | null = null;

function clearLegacyPersistentTokens(): void {
  try {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch {
    // Storage may be unavailable in restricted browser contexts.
  }
}

clearLegacyPersistentTokens();

export function getToken(): string | null {
  try { return sessionStorage.getItem(ACCESS_TOKEN_KEY); } catch { return null; }
}

export function setToken(token: string): void {
  if (getToken() !== token) { meCache = null; meCacheToken = null; }
  clearLegacyPersistentTokens();
  try { sessionStorage.setItem(ACCESS_TOKEN_KEY, token); } catch { /* keep session in memory cache only */ }
}

// Compatibility shim for old callers: refresh tokens are now HttpOnly cookies.
export function setRefreshToken(_token: string | null | undefined): void {
  clearLegacyPersistentTokens();
}

export function clearToken(): void {
  try { sessionStorage.removeItem(ACCESS_TOKEN_KEY); } catch { /* ignore */ }
  clearLegacyPersistentTokens();
  meCache = null;
  meCacheToken = null;
}

export function getCachedMe(): MeResponse | null {
  return meCacheToken === getToken() ? meCache : null;
}

export function setCachedMe(me: MeResponse | null): void {
  meCache = me;
  meCacheToken = getToken();
}
