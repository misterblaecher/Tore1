import React, { useState } from 'react'
import Layout, { btn, cardStyle, inputStyle } from '../ui/Layout'
import { api } from '../lib/api'

export default function AuditLogs() {
  const [eventId, setEventId] = useState('')
  const [items, setItems] = useState<any[]>([])
  return <Layout title="Audit logs"><div style={cardStyle()}>
    <input style={inputStyle()} value={eventId} onChange={(e) => setEventId(e.target.value)} placeholder="event id" />
    <button style={btn()} onClick={async () => {
      const data = await api<{ items: any[] }>(`/partner/portal/audit/logs?event_id=${eventId}`)
      setItems(data.items)
    }}>Load logs</button>
    {items.map((it) => <div key={it.id}>{it.action} #{it.id}</div>)}
  </div></Layout>
}
