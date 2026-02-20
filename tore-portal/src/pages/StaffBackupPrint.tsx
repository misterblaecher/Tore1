import { useEffect, useMemo, useState } from 'react'
import { ApiError, api, createShortlink } from '../lib/api'
import { useParams } from 'react-router-dom'

type BackupItem = { id: number; status: string; expiresAt?: string; suffix4: string; usedAt?: string; revokedAt?: string }
type RoleMap = Record<string, BackupItem[]>
type ListPayload = { eventId: number; roles: RoleMap }
type GeneratedCode = { code: string; suffix4: string; webUrl: string; deeplink: string; qrPayload: string; expiresAt: string }

type GeneratePayload = { eventId: number; role: string; codes: GeneratedCode[]; expiresAt: string }

type CacheEnvelope = { expiresAt: number; payload: ListPayload }

const ROLES = ['ENTRY', 'BAR', 'MANAGER', 'HELPER'] as const

function cacheKey(eventId?: string) {
  return `staff_backup_print_${eventId ?? 'unknown'}`
}

export default function StaffBackupPrint() {
  const { eventId } = useParams<{ eventId: string }>()
  const [role, setRole] = useState<(typeof ROLES)[number]>('ENTRY')
  const [count, setCount] = useState(12)
  const [list, setList] = useState<ListPayload | null>(null)
  const [generated, setGenerated] = useState<GeneratePayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [fromCache, setFromCache] = useState(false)
  const [backupShortUrl, setBackupShortUrl] = useState<string>('')

  const key = useMemo(() => cacheKey(eventId), [eventId])

  const load = async () => {
    if (!eventId) return
    try {
      const payload = await api<ListPayload>(`/events/${eventId}/staff_backup_codes`)
      setList(payload)
      localStorage.setItem(key, JSON.stringify({ payload, expiresAt: Date.now() + 24 * 60 * 60 * 1000 } satisfies CacheEnvelope))
      setFromCache(false)
      setError(null)
    } catch (e) {
      const raw = localStorage.getItem(key)
      if (raw) {
        try {
          const parsed = JSON.parse(raw) as CacheEnvelope
          if (parsed.expiresAt > Date.now()) {
            setList(parsed.payload)
            setFromCache(true)
            setError(null)
            return
          }
        } catch {
          // ignore
        }
      }
      setError(e instanceof ApiError ? e.message : 'Impossible de charger les backup codes')
    }
  }

  useEffect(() => {
    void load()
  }, [eventId])

  useEffect(() => {
    if (!eventId) return
    void (async () => {
      const id = Number(eventId)
      if (!id) return
      const short = await createShortlink({ kind: 'open_url', open_type: 'staff_backup', open_id: id })
      if (short?.shortUrl) setBackupShortUrl(short.shortUrl)
    })()
  }, [eventId])


  const generate = async () => {
    if (!eventId) return
    const idem = `backup-${eventId}-${role}-${Date.now()}`
    const payload = await api<GeneratePayload>(`/events/${eventId}/staff_backup_codes/generate`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idem },
      body: JSON.stringify({ role, count }),
    })
    setGenerated(payload)
    await load()
  }

  return (
    <main style={{ maxWidth: 900, margin: '24px auto', padding: 16 }}>
      <h1>Backup sheet staff</h1>
      <p>Codes visibles une seule fois. Stocke ce papier.</p>
      {fromCache && <p style={{ color: '#f4ba52' }}>Mode cache: dernière version sans codes bruts.</p>}
      {error && <p style={{ color: '#d76363' }}>{error}</p>}
      <section style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <select value={role} onChange={(e) => setRole(e.target.value as (typeof ROLES)[number])}>
          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <input type="number" min={1} max={24} value={count} onChange={(e) => setCount(Number(e.target.value) || 12)} />
        <button onClick={generate}>Generate backup sheet</button>
        <button onClick={() => window.print()}>Imprimer</button>
      </section>

      {generated && (
        <section>
          <h2>Codes bruts ({generated.role})</h2>
          <ul>
            {generated.codes.map((c) => (
              <li key={c.code}><strong>{c.code}</strong> · {(backupShortUrl || c.webUrl)} · fallback code: ****{c.suffix4}</li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h2>État actuel (suffix seulement)</h2>
        {ROLES.map((r) => (
          <div key={r} style={{ marginBottom: 12 }}>
            <h3>{r}</h3>
            <ul>
              {(list?.roles?.[r] ?? []).map((item) => (
                <li key={item.id}>#{item.id} · ****{item.suffix4} · {item.status} · exp {item.expiresAt ?? '-'} </li>
              ))}
            </ul>
          </div>
        ))}
      </section>
    </main>
  )
}
