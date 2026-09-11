import { apiFetch } from './api';
import { getToken, getCachedMe, MeResponse, setCachedMe } from './auth';

export async function getMe(force = false): Promise<MeResponse> {
  if (!force) {
    const cached = getCachedMe();
    if (cached) return cached;
  }

  const token = getToken();
  const me = await apiFetch<MeResponse>('/auth/me');
  // An old request must never populate the next account's profile cache.
  if (getToken() !== token) throw new Error('La session a changé.');
  setCachedMe(me);
  return me;
}
