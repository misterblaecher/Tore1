import React, { useState } from 'react'
import Layout, { btn, cardStyle, inputStyle } from '../ui/Layout'
import { api } from '../lib/api'

export default function CheckinsAdmin() {
  const [eventId, setEventId] = useState('')
  const [items, setItems] = useState<any[]>([])
  return <Layout title="Checkins admin"><div style={cardStyle()}>
    <input style={inputStyle()} value={eventId} onChange={(e) => setEventId(e.target.value)} placeholder="event id" />
    <button style={btn()} onClick={async () => {
      const data = await api<{ top_drinks: any[] }>(`/drinks/checkins/event/${eventId}`)
      setItems(data.top_drinks)
    }}>Load stats</button>
    {items.map((it) => <div key={it.name}>{it.name}: {it.count}</div>)}
  </div></Layout>
}
