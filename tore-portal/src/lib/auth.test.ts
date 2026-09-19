import { beforeEach, expect, test, vi } from 'vitest'
import { clearToken, getSession, getToken, setSession, setToken } from './auth'
import { hasOrgaHubAccess, hasOrgaManagerAccess } from './authz'
import { api, logoutPartnerSession } from './api'

beforeEach(() => {
  const localData = new Map<string, string>()
  const sessionData = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => localData.get(key) ?? null,
    setItem: (key: string, value: string) => localData.set(key, value),
    removeItem: (key: string) => localData.delete(key),
  })
  vi.stubGlobal('sessionStorage', {
    getItem: (key: string) => sessionData.get(key) ?? null,
    setItem: (key: string, value: string) => sessionData.set(key, value),
    removeItem: (key: string) => sessionData.delete(key),
  })
})

test('owner session opens the operational hub and manager tools', () => {
  setSession({ bar_id: 12, display_name: 'Owner', role: 'owner' })
  expect(hasOrgaHubAccess()).toBe(true)
  expect(hasOrgaManagerAccess()).toBe(true)
})
test('staff cannot open manager tools and logout removes role metadata', () => {
  setToken('session-token')
  setSession({ bar_id: 12, display_name: 'Staff', role: 'bartender' })
  expect(hasOrgaManagerAccess()).toBe(false)
  clearToken()
  expect(getToken()).toBeNull()
  expect(getSession()).toBeNull()
  expect(hasOrgaHubAccess()).toBe(false)
})
test('HTTP 204 is a successful deletion with the real bearer token', async () => {
  setToken('session-token')
  const request = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
  vi.stubGlobal('fetch', request)
  await expect(api('/resource/12', { method: 'DELETE' })).resolves.toBeUndefined()
  expect(request.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer session-token')
})
test('network outage does not erase the session or become a success', async () => {
  setToken('session-token')
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
  await expect(api('/resource')).rejects.toThrow('API indisponible')
  expect(getToken()).toBe('session-token')
})
test('401 clears credentials, while 403 preserves the account session', async () => {
  setToken('session-token')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 403 })))
  await expect(api('/private')).rejects.toMatchObject({ status: 403 })
  expect(getToken()).toBe('session-token')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 401 })))
  await expect(api('/private')).rejects.toMatchObject({ status: 401 })
  expect(getToken()).toBeNull()
})

test('partner credentials are tab-scoped and old localStorage values are migrated', () => {
  setToken('session-token')
  setSession({ bar_id: 12, display_name: 'Staff', role: 'bartender' })
  expect(localStorage.getItem('tore_partner_token')).toBeNull()
  expect(localStorage.getItem('tore_partner_session')).toBeNull()
  expect(sessionStorage.getItem('tore_partner_token')).toBe('session-token')

  clearToken()
  localStorage.setItem('tore_partner_token', 'legacy-token')
  expect(getToken()).toBe('legacy-token')
  expect(localStorage.getItem('tore_partner_token')).toBeNull()
  expect(sessionStorage.getItem('tore_partner_token')).toBe('legacy-token')
})

test('partner logout revokes the bearer before clearing browser state', async () => {
  setToken('session-token')
  const request = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }))
  vi.stubGlobal('fetch', request)

  await logoutPartnerSession()

  expect(request).toHaveBeenCalledTimes(1)
  expect(request.mock.calls[0][0]).toContain('/partner/auth/revoke-token')
  expect(request.mock.calls[0][1].headers.Authorization).toBe('Bearer session-token')
  expect(getToken()).toBeNull()
})
