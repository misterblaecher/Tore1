export const ACCESS_TOKEN_KEY = 'tore_site_access_token';
export const REFRESH_TOKEN_KEY = 'tore_site_refresh_token';

export type MeResponse = {
  id: string;
  display_name: string;
  email?: string | null;
  bio?: string | null;
  account_mode?: 'user' | 'organizer' | 'team';
  role_request_pending?: { requested_mode: 'user' | 'organizer' | 'team'; status: string } | null;
};

let meCache: MeResponse | null = null;

export function getToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function setRefreshToken(token: string | null | undefined): void {
  if (!token) {
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    return;
  }
  localStorage.setItem(REFRESH_TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  meCache = null;
}

export function getCachedMe(): MeResponse | null {
  return meCache;
}

export function setCachedMe(me: MeResponse | null): void {
  meCache = me;
}
