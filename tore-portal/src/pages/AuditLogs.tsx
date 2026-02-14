import React, { useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import Layout, { btn, cardStyle, inputStyle } from '../ui/Layout'
import { api } from '../lib/api'
import { CursorPager, EmptyState, InlineAlert } from '../lib/ui'

type Page = { items: any[]; next_cursor: string | null }

export default function AuditLogs() {
  const { eventId: routeEventId } = useParams()
  const [params, setParams] = useSearchParams({ event_id: routeEventId || '' })
  const [items, setItems] = useState<any[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const eventId = params.get('event_id') || ''
  const action = params.get('type') || ''

  const load = async (next?: string | null) => {
    setLoading(true)
    setError(null)
    try {
      const q = new URLSearchParams({ event_id: eventId, limit: '50' })
      if (action.trim()) q.set('type', action.trim())
      if (next) q.set('cursor', next)
      const data = await api<Page>(`/partner/portal/audit/logs?${q.toString()}`)
      setCursor(data.next_cursor)
      setItems((prev) => (next ? [...prev, ...data.items] : data.items))
    } catch (e: any) {
      setError(e?.message || 'Erreur chargement audit logs')
    } finally {
      setLoading(false)
    }
  }

  return <Layout title="Audit logs"><div style={cardStyle()}>
    <input style={inputStyle()} value={eventId} onChange={(e) => setParams({ event_id: e.target.value, type: action })} placeholder="event id" />
    <input style={{ ...inputStyle(), marginTop: 8 }} value={action} onChange={(e) => setParams({ event_id: eventId, type: e.target.value })} placeholder="action filter (type)" />
    <button style={{ ...btn(), marginTop: 8 }} onClick={() => load()} disabled={loading}>{loading ? 'Loading…' : 'Load logs'}</button>
    <CursorPager nextCursor={cursor} onNext={() => load(cursor)} />
    {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
    {!loading && items.length === 0 ? <EmptyState title="Aucun audit" /> : null}
    {items.map((it) => <div key={it.id}>{it.action} #{it.id}</div>)}
  </div></Layout>
}
