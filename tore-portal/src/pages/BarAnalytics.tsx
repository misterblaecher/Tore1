import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout, { cardStyle } from '../ui/Layout'
import { API_BASE, api } from '../lib/api'
import { getToken } from '../lib/auth'
import { Badge, Button, InlineAlert } from '../lib/ui'

type AnalyticsOut = {
  snapshot: {
    eventState: string
    lastUpdatedAt: string
  }
  orders: {
    total: number
    byStatus: {
      pending: number
      preparing: number
      ready: number
      claimed: number
      canceled: number
    }
    timelineBuckets: Array<{
      tStart: string
      tEnd: string
      ordersCount: number
      revenueTickets: number
    }>
  }
  itemsTop: Array<{
    drinkId: number
    name: string
    qty: number
    revenueTickets: number
  }>
  peak: {
    bucketStart: string
    ordersCount: number
  } | null
}

const cacheKey = (eventId: string) => `bar.analytics.v1.${eventId}`

export default function BarAnalytics() {
  const { eventId } = useParams()
  const [snapshot, setSnapshot] = useState<AnalyticsOut | null>(null)
  const [error, setError] = useState('')
  const [isOnline, setIsOnline] = useState<boolean>(typeof navigator === 'undefined' ? true : navigator.onLine)
  const [exportLoading, setExportLoading] = useState('')

  const networkMode = useMemo<'ONLINE' | 'OFFLINE'>(() => (isOnline ? 'ONLINE' : 'OFFLINE'), [isOnline])
  const isLive = snapshot?.snapshot.eventState === 'LIVE'

  const load = useCallback(async () => {
    if (!eventId) return
    if (networkMode === 'OFFLINE') {
      const cached = localStorage.getItem(cacheKey(eventId))
      if (cached) {
        setSnapshot(JSON.parse(cached))
        setError('')
      } else {
        setError('Offline: aucun cache analytics disponible.')
      }
      return
    }

    try {
      setError('')
      const data = await api<AnalyticsOut>(`/partner/portal/bar/events/${eventId}/analytics`)
      setSnapshot(data)
      localStorage.setItem(cacheKey(eventId), JSON.stringify(data))
    } catch (e: any) {
      setError(e?.message || 'Analytics indisponible')
    }
  }, [eventId, networkMode])

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
    void load()
  }, [load])

  useEffect(() => {
    if (!eventId || networkMode === 'OFFLINE' || !isLive) return
    const timer = window.setInterval(() => {
      void load()
    }, 10000)
    return () => window.clearInterval(timer)
  }, [eventId, isLive, load, networkMode])

  const downloadExport = async (path: string, filename: string, key: string) => {
    const token = getToken()
    if (!token || !eventId || networkMode === 'OFFLINE') return
    setExportLoading(key)
    try {
      const res = await fetch(`${API_BASE}${path}`, { headers: { Authorization: `Bearer ${token}` } })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      setError(e?.message || 'Export impossible')
    } finally {
      setExportLoading('')
    }
  }

  return (
    <Layout title="Analytics">
      {networkMode === 'OFFLINE' ? <InlineAlert tone="warning">OFFLINE: lecture cache seulement.</InlineAlert> : null}
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}

      <section style={{ ...cardStyle(), marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <Badge label={`EVENT ${eventId || '-'}`} tone="neutral" />
            <Badge label={`STATE ${snapshot?.snapshot.eventState || '...'}`} tone={isLive ? 'success' : 'warning'} />
            <Badge label={`NET ${networkMode}`} tone={networkMode === 'ONLINE' ? 'success' : 'warning'} />
            {eventId ? <Link to={`/bar/events/${eventId}/dashboard`}>Dashboard</Link> : null}
            {eventId ? <Link to={`/bar/events/${eventId}/orders`}>Orders</Link> : null}
            {eventId ? <Link to={`/bar/events/${eventId}/menu`}>Menu</Link> : null}
          </div>
          <Button onClick={() => void load()} disabled={!eventId || networkMode === 'OFFLINE'}>Refresh</Button>
        </div>
      </section>

      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10, marginBottom: 12 }}>
        <article style={cardStyle()}><div>Total orders</div><div style={{ fontSize: 28, fontWeight: 800 }}>{snapshot?.orders.total ?? 0}</div></article>
        <article style={cardStyle()}><div>Revenue tickets</div><div style={{ fontSize: 28, fontWeight: 800 }}>{snapshot?.orders.timelineBuckets.reduce((acc, b) => acc + b.revenueTickets, 0) ?? 0}</div></article>
        <article style={cardStyle()}><div>Peak bucket</div><div style={{ fontSize: 18, fontWeight: 800 }}>{snapshot?.peak ? `${snapshot.peak.ordersCount} ord` : '—'}</div></article>
      </section>

      <section style={{ ...cardStyle(), marginBottom: 12 }}>
        <h3 style={{ marginTop: 0 }}>Orders status</h3>
        <table style={{ width: '100%' }}>
          <tbody>
            <tr><td>Pending</td><td align="right">{snapshot?.orders.byStatus.pending ?? 0}</td></tr>
            <tr><td>Preparing</td><td align="right">{snapshot?.orders.byStatus.preparing ?? 0}</td></tr>
            <tr><td>Ready</td><td align="right">{snapshot?.orders.byStatus.ready ?? 0}</td></tr>
            <tr><td>Claimed</td><td align="right">{snapshot?.orders.byStatus.claimed ?? 0}</td></tr>
            <tr><td>Canceled</td><td align="right">{snapshot?.orders.byStatus.canceled ?? 0}</td></tr>
          </tbody>
        </table>
      </section>

      <section style={{ ...cardStyle(), marginBottom: 12 }}>
        <h3 style={{ marginTop: 0 }}>Timeline 15-min buckets</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr><th align="left">Start</th><th align="right">Orders</th><th align="right">Revenue (tix)</th><th align="left">Load</th></tr>
          </thead>
          <tbody>
            {(snapshot?.orders.timelineBuckets || []).map((bucket) => {
              const peak = snapshot?.peak?.ordersCount || 1
              const width = Math.max(2, Math.round((bucket.ordersCount / peak) * 100))
              return (
                <tr key={bucket.tStart}>
                  <td>{new Date(bucket.tStart).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                  <td align="right">{bucket.ordersCount}</td>
                  <td align="right">{bucket.revenueTickets}</td>
                  <td><div style={{ height: 8, width: `${width}%`, background: '#68d391', borderRadius: 99 }} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </section>

      <section style={{ ...cardStyle(), marginBottom: 12 }}>
        <h3 style={{ marginTop: 0 }}>Top items</h3>
        <table style={{ width: '100%' }}>
          <thead>
            <tr><th align="left">Drink</th><th align="right">Qty</th><th align="right">Revenue tix</th></tr>
          </thead>
          <tbody>
            {(snapshot?.itemsTop || []).map((item) => (
              <tr key={item.drinkId}><td>{item.name}</td><td align="right">{item.qty}</td><td align="right">{item.revenueTickets}</td></tr>
            ))}
          </tbody>
        </table>
      </section>

      <section style={{ ...cardStyle(), display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button disabled={!eventId || !!exportLoading || networkMode === 'OFFLINE'} onClick={() => void downloadExport(`/partner/portal/bar/events/${eventId}/analytics/export/orders.csv`, `orders-${eventId}.csv`, 'orders')}>Orders CSV</button>
        <button disabled={!eventId || !!exportLoading || networkMode === 'OFFLINE'} onClick={() => void downloadExport(`/partner/portal/bar/events/${eventId}/analytics/export/items.csv`, `items-${eventId}.csv`, 'items')}>Items CSV</button>
        <button disabled={!eventId || !!exportLoading || networkMode === 'OFFLINE'} onClick={() => void downloadExport(`/partner/portal/bar/events/${eventId}/analytics/export/snapshot.json`, `analytics-${eventId}.json`, 'snapshot')}>Snapshot JSON</button>
      </section>
    </Layout>
  )
}
