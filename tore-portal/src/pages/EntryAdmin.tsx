import React, { useMemo, useState } from 'react'
import Layout, { inputStyle } from '../ui/Layout'
import { api } from '../lib/api'

type EntryLog = { id: number; decision: string; reason: string; created_at: string; scan_id?: string }

type Page = { items: EntryLog[]; next_cursor: string | null }

export default function EntryAdmin() {
  const [eventId, setEventId] = useState('')
  const [search, setSearch] = useState('')
  const [logs, setLogs] = useState<EntryLog[]>([])
  const [cursor, setCursor] = useState<string | null>(null)

  const load = async (next?: string | null) => {
    const params = new URLSearchParams({ event_id: String(Number(eventId)), limit: '50' })
    if (search.trim()) params.set('search', search.trim())
    if (next) params.set('cursor', next)
    const rows = await api<Page>(`/entry/logs?${params.toString()}`)
    setCursor(rows.next_cursor)
    setLogs((prev) => (next ? [...prev, ...rows.items] : rows.items))
  }

  const stats = useMemo(() => {
    const deniedByReason: Record<string, number> = {}
    for (const row of logs) if (row.decision === 'DENY') deniedByReason[row.reason] = (deniedByReason[row.reason] || 0) + 1
    return { attempts: logs.length, denied: logs.filter((x) => x.decision === 'DENY').length, deniedByReason }
  }, [logs])

  return (
    <Layout title="Entry Admin">
      <input style={inputStyle()} placeholder="Event ID" value={eventId} onChange={(e) => setEventId(e.target.value)} />
      <input style={{ ...inputStyle(), marginTop: 8 }} placeholder="Search (scan_id/token_id)" value={search} onChange={(e) => setSearch(e.target.value)} />
      <button onClick={() => load()} style={{ marginTop: 8 }}>Charger logs</button>
      {cursor ? <button onClick={() => load(cursor)} style={{ marginLeft: 8 }}>Load more</button> : null}
      <div>Attempts: {stats.attempts}</div>
      <div>Denied: {stats.denied}</div>
      <pre>{JSON.stringify(stats.deniedByReason, null, 2)}</pre>
    </Layout>
  )
}
