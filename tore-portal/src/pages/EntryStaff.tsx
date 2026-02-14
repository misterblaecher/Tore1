import React, { useEffect, useMemo, useState } from 'react'
import Layout from '../ui/Layout'
import { API_BASE, ApiError, api } from '../lib/api'
import { getToken } from '../lib/auth'
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
type EntryStats = { entry_count: number; accepted_last_10_min: number; runtime_status?: string; runtime_reason?: string | null }

const reasonLabel = (reason: string) => {
  const labels: Record<string, string> = {
    event_paused: 'Event en pause',
    module_off: 'Module entry OFF',
    revoked: 'Accès révoqué',
    rate_limited: 'Trop de scans (cooldown)',
  }
  return labels[reason] || reason
}

export default function EntryStaff() {
  const [eventId, setEventId] = useState('')
  const [scanToken, setScanToken] = useState('')
  const [manualCode, setManualCode] = useState('')
  const [feedback, setFeedback] = useState<any>(null)
  const [logs, setLogs] = useState<EntryLog[]>([])
  const [stats, setStats] = useState<EntryStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const parsedEventId = useMemo(() => Number(eventId || 0), [eventId])

  const refreshLogs = async () => {
    if (!parsedEventId) return
    const rows = await api<EntryLogPage>(`/entry/logs?event_id=${parsedEventId}&limit=5`)
    setLogs(rows.items)
  }

  const refreshStats = async () => {
    if (!parsedEventId) return
    const data = await api<EntryStats>(`/entry/stats?event_id=${parsedEventId}`)
    setStats(data)
  }

  useEffect(() => {
    if (!parsedEventId) return
    void refreshLogs()
    void refreshStats()
    const timer = window.setInterval(() => {
      void refreshStats()
    }, 4000)
    return () => window.clearInterval(timer)
  }, [parsedEventId])

  const submitScan = async (tokenOverride?: string) => {
    if (!parsedEventId) return
    setLoading(true)
    setError('')
    try {
      const res = await api<any>('/entry/scan', {
        method: 'POST',
        body: JSON.stringify({ event_id: parsedEventId, token: tokenOverride || scanToken, scan_id: `${Date.now()}` }),
      })
      setFeedback(res)
      await Promise.all([refreshLogs(), refreshStats()])
    } catch (e) {
      if (e instanceof ApiError) {
        setError(reasonLabel(e.reason || e.message))
        setFeedback({ reason: e.reason || 'error', decision: 'DENY' })
      } else {
        setError('Erreur inattendue')
      }
    } finally {
      setLoading(false)
    }
  }

  const submitManual = async () => {
    setLoading(true)
    setError('')
    try {
      const resolved = await api<any>('/qr/resolve', {
        method: 'POST',
        body: JSON.stringify({ raw: manualCode }),
      })
      if (!resolved.valid) {
        setFeedback({ decision: 'DENY', reason: resolved.reason || 'invalid' })
        return
      }
      if (resolved.token) {
        setScanToken(resolved.token)
        await submitScan(resolved.token)
        return
      }
      setFeedback(resolved)
    } catch (e: any) {
      setError(e?.message || 'Erreur de résolution manuelle')
    } finally {
      setLoading(false)
    }
  }

  const exportCsv = async () => {
    if (!parsedEventId) return
    const token = getToken()
    if (!token) return
    const res = await fetch(`${API_BASE}/entry/logs/export?event_id=${parsedEventId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) {
      setError(`Export impossible (${res.status})`)
      return
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `entry_logs_event_${parsedEventId}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Layout title="Entry Staff">
      <div style={{ display: 'grid', gap: 12 }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input placeholder="Event ID" value={eventId} onChange={(e) => setEventId(e.target.value)} style={{ fontSize: 18, padding: 10 }} />
          <button onClick={() => void refreshStats()} disabled={!parsedEventId}>Refresh stats</button>
          <button onClick={exportCsv} disabled={!parsedEventId}>Export CSV</button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10 }}>
          <div style={{ border: '1px solid rgba(255,255,255,0.2)', borderRadius: 12, padding: 12 }}>
            <div style={{ opacity: 0.7 }}>Compteur entrées</div>
            <div style={{ fontSize: 48, fontWeight: 900 }}>{stats?.entry_count ?? 0}</div>
          </div>
          <div style={{ border: '1px solid rgba(255,255,255,0.2)', borderRadius: 12, padding: 12 }}>
            <div style={{ opacity: 0.7 }}>10 dernières minutes</div>
            <div style={{ fontSize: 42, fontWeight: 900 }}>{stats?.accepted_last_10_min ?? 0}</div>
          </div>
          <div style={{ border: '1px solid rgba(255,255,255,0.2)', borderRadius: 12, padding: 12 }}>
            <div style={{ opacity: 0.7 }}>Runtime</div>
            <div style={{ fontSize: 28, fontWeight: 900 }}>{stats?.runtime_status || '—'}</div>
            <div style={{ opacity: 0.7 }}>{stats?.runtime_reason || 'OK'}</div>
          </div>
        </div>

        <div style={{ display: 'grid', gap: 10 }}>
          <textarea
            placeholder="Scanner token"
            value={scanToken}
            onChange={(e) => setScanToken(e.target.value)}
            rows={4}
            style={{ width: '100%', fontSize: 18, padding: 10 }}
          />
          <button onClick={() => void submitScan()} disabled={loading || !parsedEventId || !scanToken.trim()} style={{ fontSize: 24, padding: '14px 12px', fontWeight: 800 }}>
            {loading ? 'Scan en cours…' : 'SCAN'}
          </button>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <input
            placeholder="Fallback code manuel"
            value={manualCode}
            onChange={(e) => setManualCode(e.target.value)}
            style={{ flex: 1, fontSize: 18, padding: 10 }}
          />
          <button onClick={() => void submitManual()} disabled={loading || !manualCode.trim()}>
            Résoudre /qr/resolve
          </button>
        </div>
      </div>

      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {feedback?.reason ? (
        <InlineAlert tone={feedback.decision === 'ACCEPT' ? 'success' : 'warning'}>
          {feedback.decision || feedback.type} — {reasonLabel(feedback.reason)}
        </InlineAlert>
      ) : null}

      <h3>5 derniers scans</h3>
      <ul>
        {logs.map((log) => (
          <li key={log.id}>
            [{new Date(log.created_at).toLocaleTimeString()}] {log.decision} - {reasonLabel(log.reason)} ({log.payload_raw})
          </li>
        ))}
      </ul>
    </Layout>
  )
}
