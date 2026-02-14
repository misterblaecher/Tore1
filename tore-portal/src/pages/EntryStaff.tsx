import React, { useState } from 'react'
import Layout from '../ui/Layout'
import { api } from '../lib/api'
import { InlineAlert } from '../lib/ui'

type EntryLog = {
  id: number
  event_id: number
  payload_raw: string
  decision: string
  reason: string
  created_at: string
}

type EntryLogPage = { items: EntryLog[]; next_cursor: string | null }

export default function EntryStaff() {
  const [eventId, setEventId] = useState('')
  const [scanToken, setScanToken] = useState('')
  const [manualCode, setManualCode] = useState('')
  const [feedback, setFeedback] = useState<any>(null)
  const [logs, setLogs] = useState<EntryLog[]>([])

  const refreshLogs = async () => {
    const rows = await api<EntryLogPage>(`/entry/logs?event_id=${Number(eventId)}&limit=20`)
    setLogs(rows.items)
  }

  const submitScan = async () => {
    const res = await api<any>('/entry/scan', {
      method: 'POST',
      body: JSON.stringify({ event_id: Number(eventId), token: scanToken, scan_id: `${Date.now()}` }),
    })
    setFeedback(res)
    await refreshLogs()
  }

  const submitManual = async () => {
    const resolved = await api<any>('/qr/resolve', {
      method: 'POST',
      body: JSON.stringify({ raw: manualCode }),
    })
    setFeedback(resolved)
    if (resolved?.type === 'manual_code' || resolved?.type === 'unknown') {
      return
    }
  }

  return (
    <Layout title="Entry Staff">
      <div style={{ display: 'grid', gap: 12 }}>
        <input placeholder="Event ID" value={eventId} onChange={(e) => setEventId(e.target.value)} />
        <textarea
          placeholder="Token scan entry"
          value={scanToken}
          onChange={(e) => setScanToken(e.target.value)}
          rows={3}
        />
        <button onClick={submitScan}>Scanner token</button>
        <input
          placeholder="Manual code (fallback terrain)"
          value={manualCode}
          onChange={(e) => setManualCode(e.target.value)}
        />
        <button onClick={submitManual}>Résoudre code manuel</button>
      </div>
      {feedback?.type === 'manual_code' ? <InlineAlert tone="warning">Code manuel détecté: {feedback?.data?.manual_code}</InlineAlert> : null}
      {feedback?.reason === 'invalid' || feedback?.type === 'unknown' ? <InlineAlert tone="error">QR/code inconnu.</InlineAlert> : null}
      {feedback ? (
        <div style={{ marginTop: 14, fontWeight: 800 }}>
          {feedback.decision || feedback.type} — {feedback.reason || 'ok'}
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
