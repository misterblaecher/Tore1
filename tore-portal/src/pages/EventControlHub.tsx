import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'
import { Badge, Button, Card, InlineAlert, Skeleton } from '../lib/ui'

const fields = ['orders_enabled', 'market_enabled', 'battles_enabled', 'hunt_enabled', 'polymarket_enabled', 'entry_enabled', 'checkins_enabled', 'wifi_enabled', 'safety_enabled']

type Snapshot = {
  event_state: 'LIVE' | 'PAUSE' | 'MENU_ONLY' | 'CLOSED' | 'SCHEDULED'
  runtime_reason?: string | null
  warnings: string[]
  modules: Record<string, { configured_enabled: boolean; effective_state: 'ON' | 'OFF' | 'READ_ONLY'; reason?: string | null }>
}

type AuditItem = {
  id: number
  action: string
  created_at: string
  payload?: Record<string, unknown>
}

export default function EventControlHub() {
  const { eventId } = useParams()
  const [state, setState] = useState<Record<string, boolean>>({})
  const [live, setLive] = useState<boolean | null>(null)
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [runtimeState, setRuntimeState] = useState('LIVE')
  const [runtimeReason, setRuntimeReason] = useState('')
  const [auditItems, setAuditItems] = useState<AuditItem[]>([])
  const [savingState, setSavingState] = useState(false)

  const refresh = async () => {
    if (!eventId) return
    const [modules, status, snap, audit] = await Promise.all([
      api<any>(`/partner/portal/event/${eventId}/modules`),
      api<any>(`/partner/portal/event/${eventId}/status`),
      api<Snapshot>(`/partner/portal/event/${eventId}/state-snapshot`),
      api<{ items: AuditItem[] }>(`/partner/portal/audit/logs?event_id=${eventId}&limit=8`),
    ])
    setState(modules)
    setLive(Boolean(status.live))
    setSnapshot(snap)
    setRuntimeState(snap.event_state)
    setRuntimeReason(snap.runtime_reason || '')
    setAuditItems(audit.items || [])
  }

  useEffect(() => {
    refresh()
  }, [eventId])

  const save = async () => {
    if (!eventId) return
    const data = await api<any>(`/partner/portal/event/${eventId}/modules`, {
      method: 'POST',
      body: JSON.stringify(state),
    })
    setState(data)
    refresh()
  }

  const saveRuntime = async () => {
    if (!eventId) return
    setSavingState(true)
    try {
      await api(`/partner/portal/event/${eventId}/state`, {
        method: 'POST',
        body: JSON.stringify({ state: runtimeState, reason: runtimeReason.trim() || null }),
      })
      await refresh()
    } finally {
      setSavingState(false)
    }
  }

  return (
    <Layout title="Event Control Hub">
      {!snapshot ? <Skeleton height={64} /> : null}
      {snapshot ? (
        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span>Event live: <b>{live ? 'YES' : 'NO'}</b></span>
            <Badge label={`STATE ${snapshot.event_state}`} tone={snapshot.event_state === 'LIVE' ? 'success' : 'warning'} />
          </div>
          <div style={{ marginTop: 10, display: 'grid', gap: 8 }}>
            <strong>Runtime manager</strong>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <select value={runtimeState} onChange={(e) => setRuntimeState(e.target.value)}>
                <option value="LIVE">LIVE</option>
                <option value="PAUSE">PAUSE</option>
                <option value="MENU_ONLY">MENU_ONLY</option>
                <option value="CLOSED">CLOSED</option>
              </select>
              <input
                value={runtimeReason}
                onChange={(e) => setRuntimeReason(e.target.value)}
                placeholder="Raison (audit)"
                style={{ minWidth: 260 }}
              />
              <Button onClick={saveRuntime} disabled={savingState}>{savingState ? 'Saving…' : 'Set state'}</Button>
            </div>
          </div>
        </Card>
      ) : null}
      {snapshot?.event_state !== 'LIVE' ? (
        <InlineAlert tone="warning">Certaines actions peuvent être forcées en READ_ONLY par l'état event.</InlineAlert>
      ) : null}
      {!state.entry_enabled || !state.wifi_enabled || !state.safety_enabled ? (
        <InlineAlert tone="error">Modules critiques manquants: entry / wifi / safety.</InlineAlert>
      ) : null}
      {fields.map((field) => (
        <label key={field} style={{ display: 'block', marginBottom: 8 }}>
          <input
            type="checkbox"
            checked={!!state[field]}
            onChange={(e) => setState((prev) => ({ ...prev, [field]: e.target.checked }))}
          />{' '}
          {field}
          {snapshot?.modules?.[field] ? <span style={{ marginLeft: 8, opacity: 0.75 }}>({snapshot.modules[field].effective_state}{snapshot.modules[field].reason ? `/${snapshot.modules[field].reason}` : ''})</span> : null}
        </label>
      ))}
      <Button onClick={save}>Save toggles</Button>
      {snapshot?.warnings?.length ? (
        <div style={{ marginTop: 14 }}>
          <Card>
          <strong>Warnings runtime override</strong>
          <ul>
            {snapshot.warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
          </Card>
        </div>
      ) : null}
      <div style={{ marginTop: 14 }}>
        <Card>
          <strong>Audit récent</strong>
          <div style={{ display: 'grid', gap: 6, marginTop: 8 }}>
            {auditItems.map((item) => (
              <div key={item.id} style={{ fontSize: 14 }}>
                [{new Date(item.created_at).toLocaleTimeString()}] {item.action}
              </div>
            ))}
            {auditItems.length === 0 ? <span style={{ opacity: 0.75 }}>Aucun audit.</span> : null}
          </div>
        </Card>
      </div>
    </Layout>
  )
}
