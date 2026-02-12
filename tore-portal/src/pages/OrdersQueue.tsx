import React, { useCallback, useEffect, useRef, useState } from 'react'
import Layout, { cardStyle } from '../ui/Layout'
import { ApiError, api } from '../lib/api'
import { getToken } from '../lib/auth'

type OrderItem = { id: number; name_snapshot: string; qty: number; line_total_cents: number }
type OrderRow = { id: number; event_id?: number | null; status: string; payment_status: 'PAID' | 'UNPAID'; note?: string | null; created_at: string; items: OrderItem[] }

const STATUSES = ['NEW', 'IN_PROGRESS', 'READY', 'SERVED', 'CANCELLED']
const DEFAULT_POLLING_MS = 5000

export default function OrdersQueue() {
  const [orders, setOrders] = useState<OrderRow[]>([])
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [eventFilter, setEventFilter] = useState<string>('')
  const [paymentFilter, setPaymentFilter] = useState<string>('')
  const [pollingMs, setPollingMs] = useState<number>(DEFAULT_POLLING_MS)
  const [newOrderIds, setNewOrderIds] = useState<Set<number>>(new Set())
  const [lastRefreshAt, setLastRefreshAt] = useState<Date | null>(null)
  const [apiStatus, setApiStatus] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(false)
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(Boolean(getToken()))
  const [soundEnabled, setSoundEnabled] = useState<boolean>(false)
  const [audioBlockedHint, setAudioBlockedHint] = useState<boolean>(false)

  const seenOrderIdsRef = useRef<Set<number>>(new Set())
  const initializedRef = useRef<boolean>(false)
  const audioContextRef = useRef<AudioContext | null>(null)

  const playAlertSound = useCallback(async () => {
    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext()
      }
      const ctx = audioContextRef.current
      if (ctx.state === 'suspended') {
        await ctx.resume()
      }

      const oscillator = ctx.createOscillator()
      const gainNode = ctx.createGain()
      oscillator.connect(gainNode)
      gainNode.connect(ctx.destination)
      oscillator.type = 'triangle'
      oscillator.frequency.value = 880

      const now = ctx.currentTime
      gainNode.gain.setValueAtTime(0.0001, now)
      gainNode.gain.exponentialRampToValueAtTime(0.12, now + 0.02)
      gainNode.gain.exponentialRampToValueAtTime(0.0001, now + 0.22)

      oscillator.start(now)
      oscillator.stop(now + 0.22)
      setAudioBlockedHint(false)
    } catch {
      setAudioBlockedHint(true)
    }
  }, [])

  const load = useCallback(async () => {
    const token = getToken()
    if (!token) {
      setIsAuthenticated(false)
      setApiStatus('Authentification requise: token absent.')
      return
    }

    setLoading(true)
    setApiStatus('')

    try {
      const params = new URLSearchParams()
      if (statusFilter) params.set('status', statusFilter)
      if (eventFilter) params.set('event_id', eventFilter)
      if (paymentFilter) params.set('payment_status', paymentFilter)
      const q = params.toString()
      const rows = await api<OrderRow[]>(`/partner/portal/orders${q ? `?${q}` : ''}`)

      const incomingNewIds = rows
        .filter((order) => order.status === 'NEW' && !seenOrderIdsRef.current.has(order.id))
        .map((order) => order.id)

      if (initializedRef.current && incomingNewIds.length > 0) {
        setNewOrderIds((prev) => {
          const next = new Set(prev)
          incomingNewIds.forEach((id) => next.add(id))
          return next
        })
        if (soundEnabled) {
          await playAlertSound()
        }
      }

      seenOrderIdsRef.current = new Set([...seenOrderIdsRef.current, ...rows.map((order) => order.id)])

      setNewOrderIds((prev) => {
        const activeNewIds = new Set(rows.filter((order) => order.status === 'NEW').map((order) => order.id))
        const next = new Set<number>()
        prev.forEach((id) => {
          if (activeNewIds.has(id)) {
            next.add(id)
          }
        })
        return next
      })

      setOrders(rows)
      setLastRefreshAt(new Date())
      setIsAuthenticated(true)
      initializedRef.current = true
    } catch (error) {
      if (!getToken()) {
        setIsAuthenticated(false)
      }

      if (error instanceof ApiError) {
        setApiStatus(`Erreur API: ${error.message}`)
      } else {
        setApiStatus('Erreur inattendue lors du refresh.')
      }
    } finally {
      setLoading(false)
    }
  }, [eventFilter, paymentFilter, playAlertSound, soundEnabled, statusFilter])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!isAuthenticated || pollingMs <= 0) {
      return
    }

    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') {
        return
      }
      if (!getToken()) {
        setIsAuthenticated(false)
        return
      }
      void load()
    }, pollingMs)

    return () => {
      window.clearInterval(timer)
    }
  }, [isAuthenticated, load, pollingMs])

  const updateStatus = async (id: number, status: string) => {
    await api(`/partner/portal/orders/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    })
    await load()
  }

  const onToggleSound = async () => {
    const next = !soundEnabled
    setSoundEnabled(next)

    if (next) {
      await playAlertSound()
    } else {
      setAudioBlockedHint(false)
    }
  }

  return (
    <Layout title="Orders Queue">
      <div style={{ ...cardStyle(), marginBottom: 12, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
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

        <select value={String(pollingMs)} onChange={(e) => setPollingMs(Number(e.target.value))}>
          <option value="3000">Refresh 3s</option>
          <option value="5000">Refresh 5s</option>
          <option value="10000">Refresh 10s</option>
          <option value="30000">Refresh 30s</option>
        </select>

        <button onClick={() => void load()} disabled={loading}>Refresh</button>
        <button onClick={() => void onToggleSound()}>{soundEnabled ? '🔔 Alert ON' : '🔕 Alert OFF'}</button>
      </div>

      <div style={{ ...cardStyle(), marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          Last refresh: {lastRefreshAt ? lastRefreshAt.toLocaleTimeString() : '—'}
          {newOrderIds.size > 0 ? <span style={{ marginLeft: 10, fontWeight: 700 }}>+{newOrderIds.size}</span> : null}
        </div>
        {audioBlockedHint && soundEnabled ? <span style={{ color: '#facc15' }}>Audio bloqué, clique pour activer l'audio.</span> : null}
      </div>

      {apiStatus ? (
        <div style={{ ...cardStyle(), marginBottom: 12, border: '1px solid #b91c1c' }}>
          <div>{apiStatus}</div>
          <button style={{ marginTop: 8 }} onClick={() => void load()} disabled={loading}>Retry</button>
        </div>
      ) : null}

      {!isAuthenticated ? (
        <div style={cardStyle()}>Session expirée ou token absent. Reconnecte-toi.</div>
      ) : null}

      {orders.map((o) => (
        <section key={o.id} style={{ ...cardStyle(), marginBottom: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <strong>#{o.id}</strong> — {o.status} {o.event_id ? `(event ${o.event_id})` : ''}
              {newOrderIds.has(o.id) ? (
                <span style={{ marginLeft: 8, padding: '2px 8px', borderRadius: 999, background: '#dc2626', color: '#fff', fontWeight: 700 }}>
                  NEW
                </span>
              ) : null}
              <span style={{ marginLeft: 8, padding: '2px 8px', borderRadius: 999, background: o.payment_status === 'PAID' ? '#14532d' : '#7f1d1d' }}>
                {o.payment_status}
              </span>
              {o.note ? <div style={{ opacity: 0.75 }}>{o.note}</div> : null}
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {o.status === 'NEW' ? <button onClick={() => void updateStatus(o.id, 'IN_PROGRESS')}>In progress</button> : null}
              {o.status === 'IN_PROGRESS' ? <button onClick={() => void updateStatus(o.id, 'READY')}>Ready</button> : null}
              {o.status === 'READY' ? <button onClick={() => void updateStatus(o.id, 'SERVED')}>Served</button> : null}
              {o.status !== 'SERVED' && o.status !== 'CANCELLED' ? <button onClick={() => void updateStatus(o.id, 'CANCELLED')}>Cancel</button> : null}
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
