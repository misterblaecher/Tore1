import React, { useEffect, useState } from 'react'
import Layout, { cardStyle } from '../ui/Layout'
import { api } from '../lib/api'

type OrderItem = { id: number; name_snapshot: string; qty: number; line_total_cents: number }
type OrderRow = { id: number; event_id?: number | null; status: string; payment_status: 'PAID' | 'UNPAID'; note?: string | null; created_at: string; items: OrderItem[] }

const STATUSES = ['NEW', 'IN_PROGRESS', 'READY', 'SERVED', 'CANCELLED']

export default function OrdersQueue() {
  const [orders, setOrders] = useState<OrderRow[]>([])
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [eventFilter, setEventFilter] = useState<string>('')
  const [paymentFilter, setPaymentFilter] = useState<string>('')

  const load = async () => {
    const params = new URLSearchParams()
    if (statusFilter) params.set('status', statusFilter)
    if (eventFilter) params.set('event_id', eventFilter)
    if (paymentFilter) params.set('payment_status', paymentFilter)
    const q = params.toString()
    const rows = await api<OrderRow[]>(`/partner/portal/orders${q ? `?${q}` : ''}`)
    setOrders(rows)
  }

  useEffect(() => {
    load()
  }, [statusFilter, eventFilter, paymentFilter])

  const updateStatus = async (id: number, status: string) => {
    await api(`/partner/portal/orders/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    })
    await load()
  }

  return (
    <Layout title="Orders Queue">
      <div style={{ ...cardStyle(), marginBottom: 12, display: 'flex', gap: 10 }}>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">Tous statuts</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={paymentFilter} onChange={(e) => setPaymentFilter(e.target.value)}>
          <option value="">Paiement: tous</option>
          <option value="PAID">PAID</option>
          <option value="UNPAID">UNPAID</option>
        </select>
        <input placeholder="event_id" value={eventFilter} onChange={(e) => setEventFilter(e.target.value)} />
      </div>
      {orders.map((o) => (
        <section key={o.id} style={{ ...cardStyle(), marginBottom: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <strong>#{o.id}</strong> — {o.status} {o.event_id ? `(event ${o.event_id})` : ''}
              <span style={{ marginLeft: 8, padding: '2px 8px', borderRadius: 999, background: o.payment_status === 'PAID' ? '#14532d' : '#7f1d1d' }}>
                {o.payment_status}
              </span>
              {o.note ? <div style={{ opacity: 0.75 }}>{o.note}</div> : null}
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {o.status === 'NEW' ? <button onClick={() => updateStatus(o.id, 'IN_PROGRESS')}>In progress</button> : null}
              {o.status === 'IN_PROGRESS' ? <button onClick={() => updateStatus(o.id, 'READY')}>Ready</button> : null}
              {o.status === 'READY' ? <button onClick={() => updateStatus(o.id, 'SERVED')}>Served</button> : null}
              {o.status !== 'SERVED' && o.status !== 'CANCELLED' ? <button onClick={() => updateStatus(o.id, 'CANCELLED')}>Cancel</button> : null}
            </div>
          </div>
          <div style={{ marginTop: 8 }}>
            {o.items.map((it) => (
              <div key={it.id}>{it.qty}x {it.name_snapshot} — {(it.line_total_cents / 100).toFixed(2)}€</div>
            ))}
          </div>
        </section>
      ))}
    </Layout>
  )
}
