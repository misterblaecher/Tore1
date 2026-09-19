export type IncidentDraft = {
  severity: string
  description: string
  location: string
  title: string
}

type StoredDraft = { draft: IncidentDraft; expiresAt: number }

export const INCIDENT_DRAFT_TTL_MS = 2 * 60 * 60 * 1000
const PREFIX = 'incident-draft-'

function key(eventId: string | number) {
  return `${PREFIX}${eventId}`
}

export function loadIncidentDraft(eventId: string | number, now = Date.now()): IncidentDraft | null {
  const storageKey = key(eventId)
  localStorage.removeItem(storageKey)
  const raw = sessionStorage.getItem(storageKey)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as StoredDraft
    if (!parsed?.draft || typeof parsed.expiresAt !== 'number' || parsed.expiresAt <= now) {
      sessionStorage.removeItem(storageKey)
      return null
    }
    return parsed.draft
  } catch {
    sessionStorage.removeItem(storageKey)
    return null
  }
}

export function saveIncidentDraft(eventId: string | number, draft: IncidentDraft, now = Date.now()) {
  const storageKey = key(eventId)
  localStorage.removeItem(storageKey)
  const empty = !draft.description.trim() && !draft.location.trim() && !draft.title.trim()
  if (empty) {
    sessionStorage.removeItem(storageKey)
    return
  }
  sessionStorage.setItem(storageKey, JSON.stringify({ draft, expiresAt: now + INCIDENT_DRAFT_TTL_MS }))
}

export function clearIncidentDraft(eventId: string | number) {
  const storageKey = key(eventId)
  localStorage.removeItem(storageKey)
  sessionStorage.removeItem(storageKey)
}

export function clearAllIncidentDrafts() {
  for (const storage of [localStorage, sessionStorage]) {
    const keys: string[] = []
    for (let index = 0; index < storage.length; index += 1) {
      const value = storage.key(index)
      if (value?.startsWith(PREFIX)) keys.push(value)
    }
    keys.forEach((value) => storage.removeItem(value))
  }
}
