import { beforeEach, describe, expect, it } from 'vitest';
import {
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
  clearToken,
  getToken,
  setRefreshToken,
  setToken,
} from '@/lib/auth';

describe('web auth storage hardening', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    clearToken();
  });

  it('keeps access tokens tab-scoped and never writes refresh tokens', () => {
    setToken('access-token');
    setRefreshToken('must-not-be-persisted');

    expect(sessionStorage.getItem(ACCESS_TOKEN_KEY)).toBe('access-token');
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull();
    expect(sessionStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull();
  });

  it('migrates the legacy access token and deletes legacy refresh material', () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, 'legacy-access');
    localStorage.setItem(REFRESH_TOKEN_KEY, 'legacy-refresh');

    expect(getToken()).toBe('legacy-access');
    expect(sessionStorage.getItem(ACCESS_TOKEN_KEY)).toBe('legacy-access');
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull();
  });

  it('clears both current and historical storage locations', () => {
    sessionStorage.setItem(ACCESS_TOKEN_KEY, 'current');
    localStorage.setItem(ACCESS_TOKEN_KEY, 'legacy');
    localStorage.setItem(REFRESH_TOKEN_KEY, 'legacy-refresh');

    clearToken();

    expect(sessionStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull();
  });
});
