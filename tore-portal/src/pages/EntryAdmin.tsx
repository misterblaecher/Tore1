import React, { useMemo, useState } from 'react'
import Layout from '../ui/Layout'
import { api } from '../lib/api'

type EntryLog = {
  id: number
  decision: string
  reason: string
  created_at: string
}

export default function EntryAdmin() {
  const [eventId, setEventId] = useState('')
  const [logs, setLogs] = useState<EntryLog[]>([])

  const load = async () => {
    const rows = await api<EntryLog[]>(`/entry/logs?event_id=${Number(eventId)}&limit=100`)
    setLogs(rows)
  }

  const stats = useMemo(() => {
    const deniedByReason: Record<string, number> = {}
    for (const row of logs) {
      if (row.decision === 'DENY') deniedByReason[row.reason] = (deniedByReason[row.reason] || 0) + 1
    }
    return { attempts: logs.length, denied: logs.filter((x) => x.decision === 'DENY').length, deniedByReason }
  }, [logs])

  return (
    <Layout title="Entry Admin">
      <input placeholder="Event ID" value={eventId} onChange={(e) => setEventId(e.target.value)} />
      <button onClick={load}>Charger logs</button>
      <div>Attempts: {stats.attempts}</div>
      <div>Denied: {stats.denied}</div>
      <pre>{JSON.stringify(stats.deniedByReason, null, 2)}</pre>
    </Layout>
  )
}
