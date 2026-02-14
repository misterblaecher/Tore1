import React, { useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import Layout, { btn, cardStyle, inputStyle } from '../ui/Layout'
import { api } from '../lib/api'
import { CursorPager, EmptyState, InlineAlert } from '../lib/ui'

type Page = { items: any[]; next_cursor: string | null }

export default function CheckinsAdmin() {
  const { eventId: routeEventId } = useParams()
  const [params, setParams] = useSearchParams({ event_id: routeEventId || '' })
  const [items, setItems] = useState<any[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const eventId = params.get('event_id') || ''
  const search = params.get('q') || ''

  const load = async (next?: string | null) => {
    setLoading(true)
    setError(null)
    try {
      const q = new URLSearchParams({ event_id: eventId, limit: '50' })
      if (search.trim()) q.set('search', search.trim())
      if (next) q.set('cursor', next)
      const data = await api<Page>(`/partner/portal/checkins/logs?${q.toString()}`)
      setItems((prev) => (next ? [...prev, ...data.items] : data.items))
      setCursor(data.next_cursor)
    } catch (e: any) {
      setError(e?.message || 'Erreur checkins')
    } finally {
      setLoading(false)
    }
  }

  return <Layout title="Checkins admin"><div style={cardStyle()}>
    <input style={inputStyle()} value={eventId} onChange={(e) => setParams({ event_id: e.target.value, q: search })} placeholder="event id" />
    <input style={{ ...inputStyle(), marginTop: 8 }} value={search} onChange={(e) => setParams({ event_id: eventId, q: e.target.value })} placeholder="search drink name" />
    <button style={{ ...btn(), marginTop: 8 }} onClick={() => load()} disabled={loading}>{loading ? 'Loading…' : 'Load logs'}</button>
    <CursorPager nextCursor={cursor} onNext={() => load(cursor)} />
    {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
    {!loading && items.length === 0 ? <EmptyState title="Aucun checkin" /> : null}
    {items.map((it) => <div key={it.id}>{it.name_snapshot} — {it.user_id}</div>)}
  </div></Layout>
}
