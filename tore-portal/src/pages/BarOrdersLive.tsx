import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout, { cardStyle } from '../ui/Layout'
import { ApiError, api } from '../lib/api'
import { Badge, Button, InlineAlert } from '../lib/ui'

type NetworkMode = 'ONLINE' | 'OFFLINE' | 'DEGRADED'
type EventState = 'LIVE' | 'PAUSE' | 'MENU_ONLY' | 'DEGRADED' | 'FROZEN' | 'CLOSED' | string

type LiveOrder = {
  id: number
  createdAt: string
  status: 'pending' | 'preparing' | 'ready' | 'claimed' | 'canceled'
  totalTickets: number
  itemsSummary: string
  customerLabel?: string | null
  expiresAt?: string | null
}

type LiveResponse = { items: LiveOrder[] }

type DashboardOut = {
  event: {
    eventState: EventState
    lastUpdatedAt: string
  }
}

const FILTERS: Array<{ key: 'all' | LiveOrder['status']; label: string }> = [
  { key: 'all', label: 'All' },
  { key: 'pending', label: 'Pending' },
  { key: 'preparing', label: 'Preparing' },
  { key: 'ready', label: 'Ready' },
  { key: 'claimed', label: 'Claimed' },
]

const actionLabel: Record<string, string> = {
  accept: 'Accept',
  ready: 'Ready',
  claim: 'Claim',
  cancel: 'Cancel',
}

function shortOrderId(id: number) {
  return `#${String(id).slice(-4)}`
}

function elapsed(createdAt: string) {
  const diff = Math.max(0, Math.floor((Date.now() - new Date(createdAt).getTime()) / 1000))
  const mm = Math.floor(diff / 60)
  const ss = diff % 60
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

function statusTone(status: LiveOrder['status']): 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'ready' || status === 'claimed') return 'success'
  if (status === 'canceled') return 'danger'
  if (status === 'preparing') return 'warning'
  return 'neutral'
}

function rowActions(status: LiveOrder['status']): Array<'accept' | 'ready' | 'claim' | 'cancel'> {
  if (status === 'pending') return ['accept', 'cancel']
  if (status === 'preparing') return ['ready', 'cancel']
  if (status === 'ready') return ['claim']
  return []
}

export default function BarOrdersLive() {
  const { eventId } = useParams()
  const [orders, setOrders] = useState<LiveOrder[]>([])
  const [eventState, setEventState] = useState<EventState>('LIVE')
  const [filter, setFilter] = useState<'all' | LiveOrder['status']>('all')
  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')
  const [loading, setLoading] = useState(false)
  const [isOnline, setIsOnline] = useState<boolean>(typeof navigator === 'undefined' ? true : navigator.onLine)
  const [pendingActions, setPendingActions] = useState<Record<number, string>>({})

  const networkMode = useMemo<NetworkMode>(() => {
    if (!isOnline) return 'OFFLINE'
    if (eventState === 'DEGRADED') return 'DEGRADED'
    return 'ONLINE'
  }, [isOnline, eventState])

  const loadEventState = useCallback(async () => {
    if (!eventId || networkMode === 'OFFLINE') return
    const snap = await api<DashboardOut>(`/partner/portal/bar/events/${eventId}/dashboard`)
    setEventState(snap.event.eventState || 'LIVE')
  }, [eventId, networkMode])

  const loadOrders = useCallback(async () => {
    if (!eventId || networkMode === 'OFFLINE') return
    setLoading(true)
    setError('')
    try {
      const res = await api<LiveResponse>(`/partner/portal/bar/events/${eventId}/orders/live?status=${filter}`)
      setOrders(res.items || [])
    } catch (e) {
      if (e instanceof ApiError) setError(e.message)
      else setError('Unable to load orders')
    } finally {
      setLoading(false)
    }
  }, [eventId, filter, networkMode])

  const refresh = useCallback(async () => {
    await loadEventState()
    await loadOrders()
  }, [loadEventState, loadOrders])

  useEffect(() => {
    const onOnline = () => setIsOnline(true)
    const onOffline = () => setIsOnline(false)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (networkMode === 'OFFLINE') return
    const delay = networkMode === 'DEGRADED' ? 5000 : 2000
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return
      void refresh()
    }, delay)
    return () => window.clearInterval(timer)
  }, [networkMode, refresh])

  const mutateStatus = async (order: LiveOrder, action: 'accept' | 'ready' | 'claim' | 'cancel') => {
    if (!eventId) return
    setActionError('')
    const actionToken = `${action}:${Date.now()}`
    setPendingActions((prev) => ({ ...prev, [order.id]: action }))

    const optimisticNext =
      action === 'accept' ? 'preparing' : action === 'ready' ? 'ready' : action === 'claim' ? 'claimed' : 'canceled'
    setOrders((prev) => prev.map((row) => (row.id === order.id ? { ...row, status: optimisticNext } : row)))

    try {
      const headers: Record<string, string> = { 'Idempotency-Key': actionToken }
      const body = action === 'cancel' ? JSON.stringify({ reason: 'bar_cancel' }) : action === 'accept' ? JSON.stringify({}) : undefined
      await api(`/partner/portal/bar/orders/${order.id}/${action}`, {
        method: 'POST',
        headers,
        body,
      })
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setActionError('Action failed: order updated by another staff member. List refreshed.')
      } else {
        setActionError('Action failed, retry.')
      }
      await refresh()
    } finally {
      setPendingActions((prev) => {
        const next = { ...prev }
        delete next[order.id]
        return next
      })
    }
  }

  return (
    <Layout title="Orders Live">
      {networkMode === 'OFFLINE' ? <InlineAlert tone="warning">OFFLINE: read-only, polling paused.</InlineAlert> : null}
      {networkMode === 'DEGRADED' ? <InlineAlert tone="warning">DEGRADED: accept/cancel blocked server-side.</InlineAlert> : null}
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {actionError ? <InlineAlert tone="warning">{actionError}</InlineAlert> : null}

      <section style={{ ...cardStyle(), marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <strong>Orders Live</strong>
            <Badge label={`EVENT ${eventId || '-'}`} tone="neutral" />
            <Badge label={`STATE ${eventState}`} tone={eventState === 'LIVE' ? 'success' : 'warning'} />
            <Badge label={`NET ${networkMode}`} tone={networkMode === 'ONLINE' ? 'success' : 'warning'} />
            {eventId ? <Link to={`/bar/events/${eventId}/dashboard`}>Dashboard</Link> : null}
            {eventId ? <Link to={`/bar/events/${eventId}/menu`}>Menu Admin</Link> : null}
            {eventId ? <Link to={`/bar/events/${eventId}/analytics`}>Analytics</Link> : null}
          </div>
          <Button onClick={() => void refresh()} disabled={!eventId || networkMode === 'OFFLINE'}>Refresh</Button>
        </div>
        <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {FILTERS.map((tab) => (
            <button key={tab.key} onClick={() => setFilter(tab.key)} style={{ fontWeight: filter === tab.key ? 700 : 500 }}>
              {tab.label}
            </button>
          ))}
        </div>
      </section>

      {loading ? <div style={{ opacity: 0.7 }}>Loading…</div> : null}
      {!loading && orders.length === 0 ? <div style={{ opacity: 0.7 }}>No orders</div> : null}

      {orders.map((row) => {
        const actionBusy = !!pendingActions[row.id]
        return (
          <article key={row.id} style={{ ...cardStyle(), marginBottom: 8, padding: 10 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr 190px', gap: 10, alignItems: 'center' }}>
              <div style={{ fontFamily: 'monospace' }}>
                <div>{elapsed(row.createdAt)}</div>
                <div>{shortOrderId(row.id)}</div>
              </div>
              <div style={{ display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 2, overflow: 'hidden' }}>
                {row.itemsSummary}
                <div style={{ opacity: 0.65 }}>{row.customerLabel || 'Guest'}</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div>{row.totalTickets} tix</div>
                <Badge label={row.status.toUpperCase()} tone={statusTone(row.status)} />
              </div>
            </div>
            <div style={{ marginTop: 8, display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              {rowActions(row.status).map((action) => (
                <button
                  key={action}
                  disabled={actionBusy || networkMode === 'OFFLINE'}
                  onClick={() => void mutateStatus(row, action)}
                >
                  {actionBusy && pendingActions[row.id] === action ? `${actionLabel[action]}...` : actionLabel[action]}
                </button>
              ))}
            </div>
          </article>
        )
      })}
    </Layout>
  )
}
