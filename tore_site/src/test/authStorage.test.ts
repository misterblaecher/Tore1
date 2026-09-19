import { beforeEach, describe, expect, test } from 'vitest'
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, clearToken, getToken, setRefreshToken, setToken } from '@/lib/auth'

describe('web token storage', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    clearToken()
  })

  test('access token is session scoped, never localStorage', () => {
    setToken('access-token')
    expect(getToken()).toBe('access-token')
    expect(sessionStorage.getItem(ACCESS_TOKEN_KEY)).toBe('access-token')
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull()
  })

  test('legacy access and refresh tokens are removed', () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, 'legacy-access')
    localStorage.setItem(REFRESH_TOKEN_KEY, 'legacy-refresh')
    setRefreshToken('must-not-be-stored')
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull()
  })
})
