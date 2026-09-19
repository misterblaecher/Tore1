export type IncidentDraft = {
  severity: 'info' | 'warn' | 'critical'
  description: string
  location: string
  title: string
}

export const INCIDENT_DRAFT_TTL_MS = 2 * 60 * 60 * 1000
const PREFIX = 'incident-draft-'

type StoredIncidentDraft = {
  eventId: string
  expiresAt: number
  draft: IncidentDraft
}

function keyFor(eventId: string | number) {
  return `${PREFIX}${String(eventId)}`
}

function isDraft(value: unknown): value is IncidentDraft {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  return (
    (item.severity === 'info' || item.severity === 'warn' || item.severity === 'critical') &&
    typeof item.description === 'string' &&
    typeof item.location === 'string' &&
    typeof item.title === 'string'
  )
}

export function loadIncidentDraft(eventId: string | number | undefined, now = Date.now()): IncidentDraft | null {
  if (eventId == null || eventId === '') return null
  const key = keyFor(eventId)
  // Never migrate sensitive legacy data into the new session-scoped store.
  try { localStorage.removeItem(key) } catch { /* unavailable storage */ }

  let raw: string | null = null
  try { raw = sessionStorage.getItem(key) } catch { return null }
  if (!raw) return null

  try {
    const stored = JSON.parse(raw) as Partial<StoredIncidentDraft>
    if (
      stored.eventId !== String(eventId) ||
      typeof stored.expiresAt !== 'number' ||
      stored.expiresAt <= now ||
      !isDraft(stored.draft)
    ) {
      sessionStorage.removeItem(key)
      return null
    }
    return stored.draft
  } catch {
    sessionStorage.removeItem(key)
    return null
  }
}

export function saveIncidentDraft(
  eventId: string | number | undefined,
  draft: IncidentDraft,
  now = Date.now(),
): void {
  if (eventId == null || eventId === '') return
  const key = keyFor(eventId)
  try { localStorage.removeItem(key) } catch { /* unavailable storage */ }
  try {
    const stored: StoredIncidentDraft = {
      eventId: String(eventId),
      expiresAt: now + INCIDENT_DRAFT_TTL_MS,
      draft,
    }
    sessionStorage.setItem(key, JSON.stringify(stored))
  } catch { /* drafting must remain usable if browser storage is unavailable */ }
}

export function clearIncidentDraft(eventId: string | number | undefined): void {
  if (eventId == null || eventId === '') return
  const key = keyFor(eventId)
  try { sessionStorage.removeItem(key) } catch { /* unavailable storage */ }
  try { localStorage.removeItem(key) } catch { /* unavailable storage */ }
}

export function clearAllIncidentDrafts(): void {
  for (const storage of [sessionStorage, localStorage]) {
    try {
      const keys: string[] = []
      for (let index = 0; index < storage.length; index += 1) {
        const key = storage.key(index)
        if (key?.startsWith(PREFIX)) keys.push(key)
      }
      keys.forEach((key) => storage.removeItem(key))
    } catch { /* unavailable storage */ }
  }
}
