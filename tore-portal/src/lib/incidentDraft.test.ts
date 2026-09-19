import { beforeEach, describe, expect, test, vi } from 'vitest'
import { clearAllIncidentDrafts, clearIncidentDraft, INCIDENT_DRAFT_TTL_MS, loadIncidentDraft, saveIncidentDraft } from './incidentDraft'

const draft = { severity: 'warn', description: 'Sensitive note', location: 'Backstage', title: 'Incident' }

function memoryStorage(): Storage {
  const values = new Map<string, string>()
  return {
    get length() { return values.size },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => Array.from(values.keys())[index] ?? null,
    removeItem: (key) => { values.delete(key) },
    setItem: (key, value) => { values.set(key, value) },
  }
}

describe('incident draft storage', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', memoryStorage())
    vi.stubGlobal('sessionStorage', memoryStorage())
  })

  test('uses sessionStorage and clears legacy localStorage', () => {
    localStorage.setItem('incident-draft-12', JSON.stringify(draft))
    saveIncidentDraft(12, draft, 1000)
    expect(localStorage.getItem('incident-draft-12')).toBeNull()
    expect(sessionStorage.getItem('incident-draft-12')).toContain('Sensitive note')
  })

  test('restores a non expired draft', () => {
    saveIncidentDraft(12, draft, 1000)
    expect(loadIncidentDraft(12, 1001)).toEqual(draft)
  })

  test('drops expired drafts', () => {
    saveIncidentDraft(12, draft, 1000)
    expect(loadIncidentDraft(12, 1000 + INCIDENT_DRAFT_TTL_MS + 1)).toBeNull()
    expect(sessionStorage.getItem('incident-draft-12')).toBeNull()
  })

  test('drops corrupt JSON without throwing', () => {
    sessionStorage.setItem('incident-draft-12', '{bad')
    expect(loadIncidentDraft(12)).toBeNull()
  })

  test('empty draft is not persisted', () => {
    saveIncidentDraft(12, { severity: 'warn', description: '', location: '', title: '' })
    expect(sessionStorage.getItem('incident-draft-12')).toBeNull()
  })

  test('clear helpers remove one or all drafts', () => {
    saveIncidentDraft(12, draft)
    saveIncidentDraft(13, draft)
    clearIncidentDraft(12)
    expect(sessionStorage.getItem('incident-draft-12')).toBeNull()
    clearAllIncidentDrafts()
    expect(sessionStorage.getItem('incident-draft-13')).toBeNull()
  })
})
