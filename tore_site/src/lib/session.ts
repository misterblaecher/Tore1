import { apiFetch } from './api';
import { clearToken, getCachedMe, MeResponse, setCachedMe } from './auth';

export async function getMe(force = false): Promise<MeResponse> {
  if (!force) {
    const cached = getCachedMe();
    if (cached) return cached;
  }

  try {
    const me = await apiFetch<MeResponse>('/auth/me');
    setCachedMe(me);
    return me;
  } catch (error) {
    clearToken();
    throw error;
  }
}
