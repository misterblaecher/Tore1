import React, { useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout, { btn, cardStyle, inputStyle } from '../ui/Layout'
import { api } from '../lib/api'

type Page = { items: any[]; next_cursor: string | null }

export default function AuditLogs() {
  const { eventId: routeEventId } = useParams()
  const [eventId, setEventId] = useState(routeEventId || '')
  const [action, setAction] = useState('')
  const [items, setItems] = useState<any[]>([])
  const [cursor, setCursor] = useState<string | null>(null)

  const load = async (next?: string | null) => {
    const params = new URLSearchParams({ event_id: eventId, limit: '50' })
    if (action.trim()) params.set('type', action.trim())
    if (next) params.set('cursor', next)
    const data = await api<Page>(`/partner/portal/audit/logs?${params.toString()}`)
    setCursor(data.next_cursor)
    setItems((prev) => (next ? [...prev, ...data.items] : data.items))
  }

  return <Layout title="Audit logs"><div style={cardStyle()}>
    <input style={inputStyle()} value={eventId} onChange={(e) => setEventId(e.target.value)} placeholder="event id" />
    <input style={{ ...inputStyle(), marginTop: 8 }} value={action} onChange={(e) => setAction(e.target.value)} placeholder="action filter (type)" />
    <button style={{ ...btn(), marginTop: 8 }} onClick={() => load()}>Load logs</button>
    {cursor ? <button style={{ ...btn('ghost'), marginTop: 8, marginLeft: 8 }} onClick={() => load(cursor)}>Load more</button> : null}
    {items.map((it) => <div key={it.id}>{it.action} #{it.id}</div>)}
  </div></Layout>
}
