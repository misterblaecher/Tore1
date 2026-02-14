import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'

type EventRow = { id: number; name: string }
type OrdersLive = { items: Array<{ id: number; status: string }> }
type AnalyticsSummary = { orders: { total_cents: number } }

export default function BarDashboard() {
  const [events, setEvents] = useState<EventRow[]>([])
  const [eventId, setEventId] = useState<number | null>(null)
  const [ordersCount, setOrdersCount] = useState(0)
  const [revenueCents, setRevenueCents] = useState(0)
  const [error, setError] = useState('')

  useEffect(() => {
    ;(async () => {
      try {
        const rows = await api<EventRow[]>('/partner/portal/events')
        setEvents(rows)
        setEventId(rows[0]?.id ?? null)
      } catch (e: any) {
        setError(e?.message || 'Impossible de charger les events')
      }
    })()
  }, [])

  const refresh = async (targetEventId: number) => {
    try {
      setError('')
      const [live, summary] = await Promise.all([
        api<OrdersLive>(`/orders/live?event_id=${targetEventId}&limit=200`),
        api<AnalyticsSummary>(`/partner/portal/analytics/summary?days=1&event_id=${targetEventId}`),
      ])
      setOrdersCount(live.items.length)
      setRevenueCents(summary.orders.total_cents || 0)
    } catch (e: any) {
      setError(e?.message || 'Snapshot indisponible')
    }
  }

  useEffect(() => {
    if (!eventId) return
    void refresh(eventId)
    const timer = window.setInterval(() => {
      void refresh(eventId)
    }, 5000)
    return () => window.clearInterval(timer)
  }, [eventId])

  const eventOptions = useMemo(() => events.map((ev) => <option key={ev.id} value={ev.id}>{ev.name}</option>), [events])

  return (
    <Layout title="Bar Dashboard">
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <select value={eventId ?? ''} onChange={(e) => setEventId(Number(e.target.value))}>
          {eventOptions}
        </select>
        <button onClick={() => eventId && void refresh(eventId)} disabled={!eventId}>Refresh</button>
      </div>

      <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 12 }}>
        <div style={{ border: '1px solid rgba(255,255,255,0.16)', borderRadius: 12, padding: 14 }}>
          <div style={{ opacity: 0.7 }}>Live orders</div>
          <div style={{ fontSize: 46, fontWeight: 900 }}>{ordersCount}</div>
        </div>
        <div style={{ border: '1px solid rgba(255,255,255,0.16)', borderRadius: 12, padding: 14 }}>
          <div style={{ opacity: 0.7 }}>Revenue snapshot (24h)</div>
          <div style={{ fontSize: 36, fontWeight: 900 }}>{(revenueCents / 100).toFixed(2)}€</div>
        </div>
      </div>

      {error ? <div style={{ color: '#ffb4b4', marginTop: 8 }}>{error}</div> : null}

      <h3 style={{ marginTop: 20 }}>Accès rapide BAR MODE</h3>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Link to="/kitchen">Kitchen</Link>
        <Link to="/orders-queue">Orders Live</Link>
        <Link to="/zones-admin">Zones</Link>
        <Link to="/menu-admin">Menu Admin</Link>
        <Link to="/wallet-admin">Wallet topup</Link>
      </div>
    </Layout>
  )
}
