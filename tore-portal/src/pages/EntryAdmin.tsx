import React, { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Layout, { inputStyle } from '../ui/Layout'
import { API_BASE, api } from '../lib/api'
import { getToken } from '../lib/auth'
import { CursorPager, EmptyState, InlineAlert } from '../lib/ui'

type EntryLog = { id: number; decision: string; reason: string; created_at: string; scan_id?: string; token_id?: number | null; staff_id?: number | null }
type Page = { items: EntryLog[]; next_cursor: string | null }
type EntryStats = {
  event_id: number
  entry_count: number
  accepted_last_10_min: number
  cap?: number | null
  cap_percent?: number | null
  runtime_status: string
  runtime_reason?: string | null
}

export default function EntryAdmin() {
  const [params, setParams] = useSearchParams()
  const [logs, setLogs] = useState<EntryLog[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState<EntryStats | null>(null)

  const eventId = params.get('event_id') || ''
  const search = params.get('q') || ''

  const load = async (next?: string | null) => {
    setLoading(true)
    setError(null)
    try {
      const q = new URLSearchParams({ event_id: String(Number(eventId)), limit: '50' })
      if (search.trim()) q.set('search', search.trim())
      if (next) q.set('cursor', next)
      const [rows, st] = await Promise.all([
        api<Page>(`/entry/logs?${q.toString()}`),
        api<EntryStats>(`/entry/stats?event_id=${Number(eventId)}`),
      ])
      setStats(st)
      setCursor(rows.next_cursor)
      setLogs((prev) => (next ? [...prev, ...rows.items] : rows.items))
    } catch (e: any) {
      setError(e?.message || 'Erreur chargement logs')
    } finally {
      setLoading(false)
    }
  }

  const exportCsv = async () => {
    if (!eventId) return
    const token = getToken()
    const res = await fetch(`${API_BASE}/entry/logs/export?event_id=${Number(eventId)}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) throw new Error(`Export HTTP ${res.status}`)
    const blob = await res.blob()
    const a = document.createElement('a')
    const url = URL.createObjectURL(blob)
    a.href = url
    a.download = `entry_logs_event_${eventId}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const statsInline = useMemo(() => {
    if (!stats) return null
    const capPart = stats.cap ? ` / cap ${stats.cap} (${stats.cap_percent ?? 0}%)` : ''
    return `Entrées: ${stats.entry_count} | Δ10min: ${stats.accepted_last_10_min}${capPart}`
  }, [stats])

  return (
    <Layout title="Entry Admin">
      <input style={inputStyle()} placeholder="Event ID" value={eventId} onChange={(e) => setParams({ event_id: e.target.value, q: search })} />
      <input style={{ ...inputStyle(), marginTop: 8 }} placeholder="Search (scan_id/token_id)" value={search} onChange={(e) => setParams({ event_id: eventId, q: e.target.value })} />
      <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button onClick={() => load()} disabled={loading}>{loading ? 'Chargement…' : 'Charger logs'}</button>
        <button onClick={exportCsv} disabled={!eventId || loading}>Export CSV</button>
      </div>

      {stats?.runtime_reason === 'event_paused' || stats?.runtime_reason === 'module_off' ? (
        <InlineAlert tone="warning">Entry en lecture bloquée: {stats.runtime_reason}</InlineAlert>
      ) : null}

      {statsInline ? <InlineAlert tone="success">{statsInline}</InlineAlert> : null}
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {!loading && logs.length === 0 ? <EmptyState title="Aucun log" body="Ajuste les filtres puis recharge." /> : null}
      <CursorPager nextCursor={cursor} onNext={() => load(cursor)} />

      <div style={{ marginTop: 10, display: 'grid', gap: 6 }}>
        {logs.map((row) => (
          <div key={row.id} style={{ border: '1px solid #2e3440', borderRadius: 8, padding: 8 }}>
            <strong>{row.decision}</strong> — {row.reason} • token:{row.token_id ?? '-'} • staff:{row.staff_id ?? '-'}
            <div style={{ fontSize: 12, opacity: 0.8 }}>{new Date(row.created_at).toLocaleString()} {row.scan_id ? `• ${row.scan_id}` : ''}</div>
          </div>
        ))}
      </div>
    </Layout>
  )
}
