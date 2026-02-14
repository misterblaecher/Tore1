import React, { useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout, { btn, cardStyle, inputStyle } from '../ui/Layout'
import { api } from '../lib/api'

type Page = { items: any[]; next_cursor: string | null }

export default function CheckinsAdmin() {
  const { eventId: routeEventId } = useParams()
  const [eventId, setEventId] = useState(routeEventId || '')
  const [search, setSearch] = useState('')
  const [items, setItems] = useState<any[]>([])
  const [cursor, setCursor] = useState<string | null>(null)

  return <Layout title="Checkins admin"><div style={cardStyle()}>
    <input style={inputStyle()} value={eventId} onChange={(e) => setEventId(e.target.value)} placeholder="event id" />
    <input style={{ ...inputStyle(), marginTop: 8 }} value={search} onChange={(e) => setSearch(e.target.value)} placeholder="search drink name" />
    <button style={{ ...btn(), marginTop: 8 }} onClick={async () => {
      const params = new URLSearchParams({ event_id: eventId, limit: '50' })
      if (search.trim()) params.set('search', search.trim())
      const data = await api<Page>(`/partner/portal/checkins/logs?${params.toString()}`)
      setItems(data.items)
      setCursor(data.next_cursor)
    }}>Load logs</button>
    {cursor ? <button style={{ ...btn('ghost'), marginLeft: 8 }} onClick={async () => {
      const params = new URLSearchParams({ event_id: eventId, limit: '50', cursor })
      if (search.trim()) params.set('search', search.trim())
      const data = await api<Page>(`/partner/portal/checkins/logs?${params.toString()}`)
      setItems((prev) => [...prev, ...data.items])
      setCursor(data.next_cursor)
    }}>Load more</button> : null}
    {items.map((it) => <div key={it.id}>{it.name_snapshot} — {it.user_id}</div>)}
  </div></Layout>
}
