import React, { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'
import { Badge, Button, Card, InlineAlert } from '../lib/ui'

type DashboardOut = {
  event: {
    eventState: 'LIVE' | 'PAUSE' | 'MENU_ONLY' | 'DEGRADED' | 'FROZEN' | 'CLOSED' | string
    lastUpdatedAt: string
  }
  ordersPending: number
  ordersPreparing: number
  ordersReady: number
  ordersTotalToday: number
  itemsSoldToday?: number | null
  revenueTicketsToday: number
  avgPrepTime?: number | null
  inventoryAlerts: Array<{ drinkId: number; name: string; status: 'LOW' | 'OUT'; remaining?: number | null }>
  lastUpdatedAt: string
}

const blockingReasons: Record<string, string> = {
  FROZEN: 'Event FROZEN: opérations bar bloquées (monitoring only).',
  CLOSED: 'Event CLOSED: service terminé (monitoring only).',
}

export default function BarDashboard() {
  const { eventId } = useParams()
  const [snapshot, setSnapshot] = useState<DashboardOut | null>(null)
  const [error, setError] = useState('')
  const [isOnline, setIsOnline] = useState<boolean>(typeof navigator === 'undefined' ? true : navigator.onLine)

  const networkMode = useMemo<'ONLINE' | 'OFFLINE' | 'DEGRADED'>(() => {
    if (!isOnline) return 'OFFLINE'
    if (snapshot?.event?.eventState === 'DEGRADED') return 'DEGRADED'
    return 'ONLINE'
  }, [isOnline, snapshot?.event?.eventState])

  const eventStateReason = useMemo(() => {
    if (!snapshot?.event?.eventState) return null
    return blockingReasons[snapshot.event.eventState] || null
  }, [snapshot?.event?.eventState])

  const refresh = async () => {
    if (!eventId || networkMode === 'OFFLINE') return
    try {
      setError('')
      const data = await api<DashboardOut>(`/partner/portal/bar/events/${eventId}/dashboard`)
      setSnapshot(data)
    } catch (e: any) {
      setError(e?.message || 'Dashboard indisponible')
    }
  }

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
    if (!eventId) return
    void refresh()
    if (networkMode === 'OFFLINE') return
    const timer = window.setInterval(() => {
      void refresh()
    }, 4000)
    return () => window.clearInterval(timer)
  }, [eventId, networkMode])

  return (
    <Layout title="BAR MODE">
      {networkMode === 'OFFLINE' ? <InlineAlert tone="warning">OFFLINE: lecture seule, polling stoppé.</InlineAlert> : null}
      {networkMode === 'DEGRADED' ? <InlineAlert tone="warning">DEGRADED: dashboard actif en read-only, writes critiques bloqués.</InlineAlert> : null}
      {eventStateReason ? <InlineAlert tone="warning">{eventStateReason}</InlineAlert> : null}
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}

      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Badge label={`EVENT ${snapshot?.event?.eventState || '...'}`} tone={snapshot?.event?.eventState === 'LIVE' ? 'success' : 'warning'} />
            <Badge label={`NET ${networkMode}`} tone={networkMode === 'ONLINE' ? 'success' : 'warning'} />
          </div>
          <Button onClick={() => void refresh()} disabled={!eventId || networkMode === 'OFFLINE'}>Refresh</Button>
        </div>
        <div style={{ marginTop: 8, opacity: 0.75, fontSize: 13 }}>
          Last update: {snapshot?.lastUpdatedAt ? new Date(snapshot.lastUpdatedAt).toLocaleTimeString() : 'n/a'}
        </div>
      </Card>

      <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10 }}>
        <Card><div style={{ opacity: 0.7 }}>Orders live</div><div style={{ fontSize: 30, fontWeight: 900 }}>{snapshot?.ordersPending ?? 0}</div></Card>
        <Card><div style={{ opacity: 0.7 }}>Revenue tickets (today)</div><div style={{ fontSize: 30, fontWeight: 900 }}>{snapshot?.revenueTicketsToday ?? 0}</div></Card>
        <Card><div style={{ opacity: 0.7 }}>Items sold (today)</div><div style={{ fontSize: 30, fontWeight: 900 }}>{snapshot?.itemsSoldToday ?? 0}</div></Card>
        <Card><div style={{ opacity: 0.7 }}>Avg prep (sec)</div><div style={{ fontSize: 30, fontWeight: 900 }}>{snapshot?.avgPrepTime ? Math.round(snapshot.avgPrepTime) : '—'}</div></Card>
      </div>

      <Card>
        <h3 style={{ marginTop: 0 }}>Orders status</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 8 }}>
          <div>Pending: <strong>{snapshot?.ordersPending ?? 0}</strong></div>
          <div>Preparing: <strong>{snapshot?.ordersPreparing ?? 0}</strong></div>
          <div>Ready: <strong>{snapshot?.ordersReady ?? 0}</strong></div>
          <div>Total today: <strong>{snapshot?.ordersTotalToday ?? 0}</strong></div>
        </div>
      </Card>

      {snapshot && snapshot.inventoryAlerts.length > 0 ? (
        <Card>
          <h3 style={{ marginTop: 0 }}>Alerts</h3>
          <div style={{ display: 'grid', gap: 6 }}>
            {snapshot.inventoryAlerts.map((alert) => (
              <div key={`${alert.drinkId}-${alert.status}`}>
                {alert.name} — <strong>{alert.status}</strong>{typeof alert.remaining === 'number' ? ` (${alert.remaining} left)` : ''}
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      <Card>
        <h3 style={{ marginTop: 0 }}>BAR MODE modules</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Link to={eventId ? `/bar/events/${eventId}/orders` : '/orders-queue'}>Orders Live</Link>
          <Link to={eventId ? `/bar/events/${eventId}/menu` : "/menu-admin"}>Menu Admin</Link>
          <Link to={eventId ? `/bar/events/${eventId}/analytics` : '/analytics'}>Analytics</Link>
        </div>
        <div style={{ marginTop: 10 }}>
          <Link to={eventId ? `/bar/events/${eventId}/orders` : '/orders-queue'}>Go to Orders Live</Link>
        </div>
      </Card>
    </Layout>
  )
}
