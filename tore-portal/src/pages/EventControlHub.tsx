import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'
import { Badge, Button, Card, InlineAlert, Skeleton } from '../lib/ui'

const fields = ['orders_enabled', 'market_enabled', 'battles_enabled', 'hunt_enabled', 'polymarket_enabled', 'entry_enabled', 'checkins_enabled', 'wifi_enabled', 'safety_enabled']

type Snapshot = {
  event_state: 'LIVE' | 'PAUSE' | 'MENU_ONLY' | 'CLOSED' | 'SCHEDULED'
  warnings: string[]
  modules: Record<string, { configured_enabled: boolean; effective_state: 'ON' | 'OFF' | 'READ_ONLY' }>
}

export default function EventControlHub() {
  const { eventId } = useParams()
  const [state, setState] = useState<Record<string, boolean>>({})
  const [live, setLive] = useState<boolean | null>(null)
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)

  const refresh = async () => {
    if (!eventId) return
    const [modules, status, snap] = await Promise.all([
      api<any>(`/partner/portal/event/${eventId}/modules`),
      api<any>(`/partner/portal/event/${eventId}/status`),
      api<Snapshot>(`/partner/portal/event/${eventId}/state-snapshot`),
    ])
    setState(modules)
    setLive(Boolean(status.live))
    setSnapshot(snap)
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

  return (
    <Layout title="Event Control Hub">
      {!snapshot ? <Skeleton height={64} /> : null}
      {snapshot ? (
        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span>Event live: <b>{live ? 'YES' : 'NO'}</b></span>
            <Badge label={`STATE ${snapshot.event_state}`} tone={snapshot.event_state === 'LIVE' ? 'success' : 'warning'} />
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
          {snapshot?.modules?.[field] ? <span style={{ marginLeft: 8, opacity: 0.75 }}>({snapshot.modules[field].effective_state})</span> : null}
        </label>
      ))}
      <Button onClick={save}>Save toggles</Button>
    </Layout>
  )
}
