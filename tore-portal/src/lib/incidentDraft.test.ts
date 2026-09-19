import { beforeEach, expect, test, vi } from 'vitest'
import { clearToken } from './auth'
import {
  INCIDENT_DRAFT_TTL_MS,
  clearAllIncidentDrafts,
  loadIncidentDraft,
  saveIncidentDraft,
} from './incidentDraft'

function storageStub() {
  const data = new Map<string, string>()
  return {
    get length() { return data.size },
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
    clear: () => data.clear(),
    key: (index: number) => Array.from(data.keys())[index] ?? null,
  }
}

beforeEach(() => {
  vi.stubGlobal('localStorage', storageStub())
  vi.stubGlobal('sessionStorage', storageStub())
})

const draft = {
  severity: 'critical' as const,
  description: 'Personne blessée',
  location: 'Entrée',
  title: 'Incident médical',
}

test('incident drafts are session-scoped and never persisted in localStorage', () => {
  saveIncidentDraft('42', draft, 1_000)
  expect(localStorage.getItem('incident-draft-42')).toBeNull()
  expect(sessionStorage.getItem('incident-draft-42')).toContain('Personne blessée')
  expect(loadIncidentDraft('42', 2_000)).toEqual(draft)
})

test('expired incident drafts are ignored and deleted', () => {
  saveIncidentDraft('42', draft, 1_000)
  expect(loadIncidentDraft('42', 1_000 + INCIDENT_DRAFT_TTL_MS + 1)).toBeNull()
  expect(sessionStorage.getItem('incident-draft-42')).toBeNull()
})

test('corrupt or wrong-event drafts are never restored', () => {
  sessionStorage.setItem('incident-draft-42', '{invalid-json')
  expect(loadIncidentDraft('42')).toBeNull()
  expect(sessionStorage.getItem('incident-draft-42')).toBeNull()

  sessionStorage.setItem('incident-draft-42', JSON.stringify({
    eventId: '99',
    expiresAt: Date.now() + 10_000,
    draft,
  }))
  expect(loadIncidentDraft('42')).toBeNull()
  expect(sessionStorage.getItem('incident-draft-42')).toBeNull()
})

test('legacy localStorage incident data is deleted instead of migrated', () => {
  localStorage.setItem('incident-draft-42', JSON.stringify(draft))
  expect(loadIncidentDraft('42')).toBeNull()
  expect(localStorage.getItem('incident-draft-42')).toBeNull()
  expect(sessionStorage.getItem('incident-draft-42')).toBeNull()
})

test('logout clears all incident drafts across current and legacy storage', () => {
  saveIncidentDraft('42', draft)
  sessionStorage.setItem('incident-draft-43', 'anything')
  localStorage.setItem('incident-draft-44', 'legacy')
  sessionStorage.setItem('unrelated', 'keep')

  clearToken()

  expect(sessionStorage.getItem('incident-draft-42')).toBeNull()
  expect(sessionStorage.getItem('incident-draft-43')).toBeNull()
  expect(localStorage.getItem('incident-draft-44')).toBeNull()
  expect(sessionStorage.getItem('unrelated')).toBe('keep')
})

test('clearAllIncidentDrafts only removes incident keys', () => {
  sessionStorage.setItem('incident-draft-1', 'one')
  localStorage.setItem('incident-draft-2', 'two')
  localStorage.setItem('other-key', 'keep')
  clearAllIncidentDrafts()
  expect(sessionStorage.getItem('incident-draft-1')).toBeNull()
  expect(localStorage.getItem('incident-draft-2')).toBeNull()
  expect(localStorage.getItem('other-key')).toBe('keep')
})
