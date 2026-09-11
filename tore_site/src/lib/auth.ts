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

export function getToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setToken(token: string): void {
  if (getToken() !== token) { meCache = null; meCacheToken = null; }
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
  meCacheToken = null;
}

export function getCachedMe(): MeResponse | null {
  return meCacheToken === getToken() ? meCache : null;
}

export function setCachedMe(me: MeResponse | null): void {
  meCache = me;
  meCacheToken = getToken();
}
