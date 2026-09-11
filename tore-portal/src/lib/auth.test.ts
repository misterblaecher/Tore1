import { beforeEach, expect, test, vi } from 'vitest'
import { clearToken, getSession, getToken, setSession, setToken } from './auth'
import { hasOrgaHubAccess, hasOrgaManagerAccess } from './authz'
import { api } from './api'

beforeEach(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
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
