import React, { useState } from 'react'
import Layout from '../ui/Layout'
import { api } from '../lib/api'

type EntryLog = {
  id: number
  event_id: number
  payload_raw: string
  decision: string
  reason: string
  created_at: string
}

export default function EntryStaff() {
  const [eventId, setEventId] = useState('')
  const [scan, setScan] = useState('')
  const [feedback, setFeedback] = useState<any>(null)
  const [logs, setLogs] = useState<EntryLog[]>([])

  const submit = async () => {
    const res = await api<any>('/entry/scan', {
      method: 'POST',
      body: JSON.stringify({ event_id: Number(eventId), raw_payload: scan, scan_id: `${Date.now()}` }),
    })
    setFeedback(res)
    const rows = await api<EntryLog[]>(`/entry/logs?event_id=${Number(eventId)}&limit=20`)
    setLogs(rows)
  }

  return (
    <Layout title="Entry Staff">
      <div style={{ display: 'grid', gap: 12 }}>
        <input placeholder="Event ID" value={eventId} onChange={(e) => setEventId(e.target.value)} />
        <textarea
          placeholder="Scan QR ou code manuel (ex: tore://entry?event_id=1 ou user:abc)"
          value={scan}
          onChange={(e) => setScan(e.target.value)}
          rows={4}
        />
        <button onClick={submit}>Scanner</button>
      </div>
      {feedback ? (
        <div style={{ marginTop: 14, fontWeight: 800, color: feedback.decision === 'ALLOW' ? '#4dff88' : '#ff7878' }}>
          {feedback.decision} — {feedback.reason}
        </div>
      ) : null}
      <h3>Derniers scans</h3>
      <ul>
        {logs.map((log) => (
          <li key={log.id}>
            [{new Date(log.created_at).toLocaleTimeString()}] {log.decision} - {log.reason} ({log.payload_raw})
          </li>
        ))}
      </ul>
    </Layout>
  )
}
