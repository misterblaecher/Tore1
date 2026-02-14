import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout, { cardStyle } from '../ui/Layout'
import { api } from '../lib/api'

const fields = ['orders_enabled', 'market_enabled', 'battles_enabled', 'hunt_enabled', 'polymarket_enabled', 'entry_enabled', 'checkins_enabled', 'wifi_enabled', 'safety_enabled']

export default function EventControlHub() {
  const { eventId } = useParams()
  const [state, setState] = useState<Record<string, boolean>>({})
  const [live, setLive] = useState<boolean | null>(null)

  const refresh = async () => {
    if (!eventId) return
    const [modules, status] = await Promise.all([
      api<any>(`/partner/portal/event/${eventId}/modules`),
      api<any>(`/partner/portal/event/${eventId}/status`),
    ])
    setState(modules)
    setLive(Boolean(status.live))
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
  }

  return (
    <Layout title="Event Control Hub">
      <div style={{ ...cardStyle(), marginBottom: 12 }}>Event live: <b>{live ? 'YES' : 'NO'}</b></div>
      {!state.entry_enabled || !state.wifi_enabled || !state.safety_enabled ? (
        <div style={{ ...cardStyle(), marginBottom: 12, borderColor: 'rgba(255,120,120,0.45)' }}>Warning: one or more key modules are disabled.</div>
      ) : null}
      {fields.map((field) => (
        <label key={field} style={{ display: 'block', marginBottom: 8 }}>
          <input
            type="checkbox"
            checked={!!state[field]}
            onChange={(e) => setState((prev) => ({ ...prev, [field]: e.target.checked }))}
          />{' '}
          {field}
        </label>
      ))}
      <button onClick={save}>Save toggles</button>
    </Layout>
  )
}
