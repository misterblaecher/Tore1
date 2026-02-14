import React, { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Layout, { inputStyle } from '../ui/Layout'
import { api } from '../lib/api'
import { CursorPager, EmptyState, InlineAlert } from '../lib/ui'

type EntryLog = { id: number; decision: string; reason: string; created_at: string; scan_id?: string }
type Page = { items: EntryLog[]; next_cursor: string | null }

export default function EntryAdmin() {
  const [params, setParams] = useSearchParams()
  const [logs, setLogs] = useState<EntryLog[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const eventId = params.get('event_id') || ''
  const search = params.get('q') || ''

  const load = async (next?: string | null) => {
    setLoading(true)
    setError(null)
    try {
      const q = new URLSearchParams({ event_id: String(Number(eventId)), limit: '50' })
      if (search.trim()) q.set('search', search.trim())
      if (next) q.set('cursor', next)
      const rows = await api<Page>(`/entry/logs?${q.toString()}`)
      setCursor(rows.next_cursor)
      setLogs((prev) => (next ? [...prev, ...rows.items] : rows.items))
    } catch (e: any) {
      setError(e?.message || 'Erreur chargement logs')
    } finally {
      setLoading(false)
    }
  }

  const stats = useMemo(() => {
    const deniedByReason: Record<string, number> = {}
    for (const row of logs) if (row.decision === 'DENY') deniedByReason[row.reason] = (deniedByReason[row.reason] || 0) + 1
    return { attempts: logs.length, denied: logs.filter((x) => x.decision === 'DENY').length, deniedByReason }
  }, [logs])

  return (
    <Layout title="Entry Admin">
      <input style={inputStyle()} placeholder="Event ID" value={eventId} onChange={(e) => setParams({ event_id: e.target.value, q: search })} />
      <input style={{ ...inputStyle(), marginTop: 8 }} placeholder="Search (scan_id/token_id)" value={search} onChange={(e) => setParams({ event_id: eventId, q: e.target.value })} />
      <button onClick={() => load()} style={{ marginTop: 8 }} disabled={loading}>{loading ? 'Chargement…' : 'Charger logs'}</button>
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {!loading && logs.length === 0 ? <EmptyState title="Aucun log" body="Ajuste les filtres puis recharge." /> : null}
      <CursorPager nextCursor={cursor} onNext={() => load(cursor)} />
      <div>Attempts: {stats.attempts}</div>
      <div>Denied: {stats.denied}</div>
      <pre>{JSON.stringify(stats.deniedByReason, null, 2)}</pre>
    </Layout>
  )
}
