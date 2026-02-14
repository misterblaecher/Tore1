import React, { useCallback, useEffect, useState } from 'react'
import Layout, { cardStyle } from '../ui/Layout'
import { ApiError, api } from '../lib/api'
import { CursorPager, EmptyState, InlineAlert } from '../lib/ui'

type OrderItem = { id: number; name_snapshot: string; qty: number; line_total_cents: number }
type OrderRow = { id: number; event_id?: number | null; status: string; payment_status: 'PAID' | 'UNPAID'; note?: string | null; created_at: string; items: OrderItem[] }
type LiveResponse = { items: OrderRow[]; next_cursor?: string | null }

const STATUS_TABS = [
  { key: '', label: 'Tous' },
  { key: 'pending', label: 'Pending' },
  { key: 'accepted', label: 'Accepted' },
  { key: 'ready', label: 'Ready' },
]

const BLOCKED_REASONS = new Set(['event_paused', 'module_off', 'revoked'])

export default function OrdersQueue() {
  const [orders, setOrders] = useState<OrderRow[]>([])
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [eventFilter, setEventFilter] = useState<string>('')
  const [cursor, setCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string>('')
  const [reason, setReason] = useState<string>('')

  const load = useCallback(async (append = false) => {
    if (!eventFilter) {
      setOrders([])
      setCursor(null)
      return
    }
    setLoading(true)
    setError('')
    setReason('')
    try {
      const params = new URLSearchParams({ event_id: eventFilter, limit: '50' })
      if (statusFilter) params.set('status', statusFilter)
      if (append && cursor) params.set('cursor', cursor)
      const res = await api<LiveResponse>(`/orders/live?${params.toString()}`)
      setOrders((prev) => (append ? [...prev, ...res.items] : res.items))
      setCursor(res.next_cursor ?? null)
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.status === 429 ? 'Trop de requêtes, réessaie.' : e.message)
        setReason(e.reason ?? '')
      } else setError('Erreur inattendue')
    } finally {
      setLoading(false)
    }
  }, [cursor, eventFilter, statusFilter])

  useEffect(() => {
    void load(false)
  }, [load])

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return
      if (!eventFilter) return
      void load(false)
    }, 2500)
    return () => window.clearInterval(timer)
  }, [eventFilter, load])

  const updateStatus = async (id: number, status: string) => {
    try {
      await api(`/orders/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) })
      await load(false)
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.status === 429 ? 'Trop de requêtes, réessaie.' : e.message)
        setReason(e.reason ?? '')
      }
    }
  }

  const readOnly = BLOCKED_REASONS.has(reason)

  const actions = (status: string, id: number) => {
    if (readOnly) return null
    if (status === 'NEW') return <button onClick={() => void updateStatus(id, 'accepted')}>Accept</button>
    if (status === 'IN_PROGRESS') return <button onClick={() => void updateStatus(id, 'ready')}>Ready</button>
    if (status === 'READY') return <button onClick={() => void updateStatus(id, 'completed')}>Complete</button>
    return null
  }

  return (
    <Layout title="Orders Live">
      <div style={{ ...cardStyle(), marginBottom: 12, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <input placeholder="event_id" value={eventFilter} onChange={(e) => setEventFilter(e.target.value)} />
        {STATUS_TABS.map((tab) => (
          <button key={tab.key} onClick={() => setStatusFilter(tab.key)} style={{ fontWeight: statusFilter === tab.key ? 700 : 500 }}>{tab.label}</button>
        ))}
        <button onClick={() => void load(false)} disabled={loading || !eventFilter}>Refresh</button>
      </div>

      {readOnly ? <InlineAlert tone="warning">Actions désactivées ({reason}).</InlineAlert> : null}
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {!eventFilter ? <EmptyState title="Saisis un event_id" body="Le live orders nécessite un event_id." /> : null}
      {eventFilter && !loading && orders.length === 0 ? <EmptyState title="Aucune commande" /> : null}

      {orders.map((o) => (
        <section key={o.id} style={{ ...cardStyle(), marginBottom: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <strong>#{o.id}</strong> — {o.status}
              {o.note ? <div style={{ opacity: 0.75 }}>{o.note}</div> : null}
            </div>
            {actions(o.status, o.id)}
          </div>
          <div style={{ marginTop: 8 }}>
            {o.items.map((it) => (
              <div key={it.id}>{it.qty}x {it.name_snapshot} — {(it.line_total_cents / 100).toFixed(2)}€</div>
            ))}
          </div>
        </section>
      ))}

      <CursorPager nextCursor={cursor} onNext={() => void load(true)} />
    </Layout>
  )
}
