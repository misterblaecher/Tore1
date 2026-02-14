import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'

const fields = ['orders_enabled', 'market_enabled', 'battles_enabled', 'hunt_enabled', 'polymarket_enabled', 'entry_enabled']

export default function EventControlHub() {
  const { eventId } = useParams()
  const [state, setState] = useState<Record<string, boolean>>({})

  useEffect(() => {
    ;(async () => {
      if (!eventId) return
      const data = await api<any>(`/partner/portal/event/${eventId}/modules`)
      setState(data)
    })()
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
      {fields.map((field) => (
        <label key={field} style={{ display: 'block' }}>
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
