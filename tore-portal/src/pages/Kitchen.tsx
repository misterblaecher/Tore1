import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { ApiError, api } from '../lib/api'
import { EmptyState, InlineAlert } from '../lib/ui'

type OrderItem = { id: number; name_snapshot: string; qty: number }
type OrderRow = {
  id: number
  bar_id?: number | null
  status: string
  status_alias?: string
  runtime_status?: string
  created_at: string
  note?: string | null
  zone_id?: number | null
  zone_name?: string | null
  items: OrderItem[]
}
type LiveResponse = { items: OrderRow[]; next_cursor?: string | null }
type BarOut = { id: number; name: string }
type ZoneRow = { id: number; name: string }
type ZonesOut = { items: ZoneRow[] }

type KitchenColumn = 'pending' | 'accepted' | 'ready'

type ZoneOption = { value: string; label: string }

const MAX_ORDERS = 200
const LIVE_LIMIT = 100
const BLOCKED_REASONS = new Set(['event_paused', 'module_off', 'revoked'])

const columnLabels: Record<KitchenColumn, string> = {
  pending: 'PENDING',
  accepted: 'ACCEPTED',
  ready: 'READY',
}

const statusToColumn = (order: OrderRow): KitchenColumn | null => {
  const normalized = (order.status_alias || order.status || '').toLowerCase()
  if (normalized === 'pending' || order.status === 'NEW') return 'pending'
  if (normalized === 'accepted' || order.status === 'IN_PROGRESS') return 'accepted'
  if (normalized === 'ready' || order.status === 'READY') return 'ready'
  return null
}

const reasonLabel = (reason: string) => {
  const map: Record<string, string> = {
    event_paused: 'Event en pause: actions temporairement bloquées.',
    module_off: 'Module Orders désactivé pour cet event.',
    revoked: 'Accès révoqué côté backend.',
    rate_limited: 'Trop de requêtes. Cooldown actif quelques secondes.',
  }
  return map[reason] || reason
}

const formatElapsed = (createdAt: string) => {
  const diff = Math.max(0, Math.floor((Date.now() - new Date(createdAt).getTime()) / 1000))
  const mm = Math.floor(diff / 60)
  const ss = diff % 60
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

const shortOrderId = (id: number) => `#${String(id).slice(-4)}`

const zoneKey = (order: OrderRow) => (order.zone_id == null ? 'none' : String(order.zone_id))
const zoneLabel = (order: OrderRow) => {
  if (order.zone_name && order.zone_name.trim()) return order.zone_name.trim()
  if (order.zone_id != null) return `Zone ${order.zone_id}`
  return 'Sans zone'
}

export default function Kitchen() {
  const [eventId, setEventId] = useState('')
  const [zoneFilter, setZoneFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [orders, setOrders] = useState<OrderRow[]>([])
  const [zones, setZones] = useState<ZoneRow[]>([])
  const [groupByZone, setGroupByZone] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [reason, setReason] = useState('')
  const [cooldownUntil, setCooldownUntil] = useState(0)

  useEffect(() => {
    ;(async () => {
      try {
        const bar = await api<BarOut>('/partner/portal/bar')
        const data = await api<ZonesOut>(`/bars/${bar.id}/zones?limit=200`)
        setZones(data.items || [])
      } catch {
        setZones([])
      }
    })()
  }, [])

  const loadOrders = useCallback(async () => {
    if (!eventId || document.visibilityState !== 'visible') return
    setLoading(true)
    setError('')
    setReason('')
    try {
      const base = new URLSearchParams({ event_id: eventId, limit: String(LIVE_LIMIT) })
      let nextCursor: string | null = null
      let collected: OrderRow[] = []
      for (let page = 0; page < 3 && collected.length < MAX_ORDERS; page += 1) {
        const params = new URLSearchParams(base)
        if (nextCursor) params.set('cursor', nextCursor)
        const res = await api<LiveResponse>(`/orders/live?${params.toString()}`)
        collected = [...collected, ...res.items]
        nextCursor = res.next_cursor ?? null
        if (!nextCursor || res.items.length === 0) break
      }
      setOrders(collected.slice(0, MAX_ORDERS))
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.status === 429 ? 'Trop de requêtes, réessaie.' : e.message)
        setReason(e.reason ?? '')
      } else {
        setError('Erreur inattendue')
      }
    } finally {
      setLoading(false)
    }
  }, [eventId])

  useEffect(() => {
    void loadOrders()
  }, [loadOrders])

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return
      void loadOrders()
    }, 2000)
    return () => window.clearInterval(timer)
  }, [loadOrders])

  const blocked = BLOCKED_REASONS.has(reason)
  const cooldownLeft = Math.max(0, Math.ceil((cooldownUntil - Date.now()) / 1000))
  const buttonsDisabled = blocked || cooldownLeft > 0

  const updateStatus = async (id: number, status: 'accepted' | 'ready' | 'completed') => {
    if (buttonsDisabled) return
    try {
      await api(`/orders/${id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      })
      await loadOrders()
    } catch (e) {
      if (e instanceof ApiError) {
        setReason(e.reason ?? '')
        setError(e.status === 429 ? 'Trop de requêtes, réessaie.' : e.message)
        if (e.status === 429 || e.reason === 'rate_limited') {
          setCooldownUntil(Date.now() + 8000)
        }
      }
    }
  }

  const filteredOrders = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return orders.filter((order) => {
      if (zoneFilter !== 'all' && zoneKey(order) !== zoneFilter) return false
      if (!needle) return true
      const inItems = order.items.some((it) => it.name_snapshot.toLowerCase().includes(needle))
      return `${order.id}`.includes(needle) || zoneLabel(order).toLowerCase().includes(needle) || inItems
    })
  }, [orders, search, zoneFilter])

  const zoneOptions = useMemo<ZoneOption[]>(() => {
    const map = new Map<string, string>()
    map.set('none', 'Sans zone')
    for (const zone of zones) map.set(String(zone.id), zone.name)
    for (const order of orders) map.set(zoneKey(order), zoneLabel(order))
    return [{ value: 'all', label: 'All zones' }, ...Array.from(map.entries()).map(([value, label]) => ({ value, label }))]
  }, [orders, zones])

  const columns = useMemo(() => {
    const grouped: Record<KitchenColumn, OrderRow[]> = {
      pending: [],
      accepted: [],
      ready: [],
    }
    for (const order of filteredOrders) {
      const target = statusToColumn(order)
      if (target) grouped[target].push(order)
    }
    return grouped
  }, [filteredOrders])

  return (
    <div style={{ minHeight: '100vh', background: '#09090f', color: '#fff', padding: 16 }}>
      <header style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
        <h1 style={{ fontSize: 32, margin: 0, letterSpacing: 1 }}>Kitchen Mode</h1>
        <input placeholder="event_id" value={eventId} onChange={(e) => setEventId(e.target.value)} style={{ fontSize: 18, padding: '8px 10px' }} />
        <select value={zoneFilter} onChange={(e) => setZoneFilter(e.target.value)} style={{ fontSize: 18, padding: '8px 10px' }}>
          {zoneOptions.map((zone) => <option key={zone.value} value={zone.value}>{zone.label}</option>)}
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 16 }}>
          <input type="checkbox" checked={groupByZone} onChange={(e) => setGroupByZone(e.target.checked)} />
          Grouper par zone
        </label>
        <input placeholder="Search item / order" value={search} onChange={(e) => setSearch(e.target.value)} style={{ fontSize: 18, padding: '8px 10px', minWidth: 260 }} />
        <button onClick={() => void loadOrders()} disabled={!eventId || loading} style={{ fontSize: 18, padding: '8px 14px' }}>Refresh</button>
      </header>

      {blocked ? <InlineAlert tone="warning">{reasonLabel(reason)} Actions désactivées.</InlineAlert> : null}
      {reason === 'rate_limited' || cooldownLeft > 0 ? <InlineAlert tone="warning">{reasonLabel('rate_limited')} {cooldownLeft > 0 ? `(${cooldownLeft}s)` : ''}</InlineAlert> : null}
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {!eventId ? <EmptyState title="Saisis un event_id" body="Le mode cuisine nécessite un event_id." /> : null}

      <main style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12, marginTop: 12 }}>
        {(Object.keys(columns) as KitchenColumn[]).map((col) => {
          const byZone = new Map<string, OrderRow[]>()
          if (groupByZone) {
            for (const order of columns[col]) {
              const key = zoneKey(order)
              const bucket = byZone.get(key)
              if (bucket) bucket.push(order)
              else byZone.set(key, [order])
            }
          }
          const sections = groupByZone
            ? Array.from(byZone.entries()).map(([key, rows]) => ({ key, title: zoneLabel(rows[0]), rows }))
            : [{ key: 'all', title: '', rows: columns[col] }]
          return (
            <section key={col} style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 12, padding: 10, minHeight: '80vh' }}>
              <h2 style={{ margin: '0 0 8px', fontSize: 24 }}>{columnLabels[col]} ({columns[col].length})</h2>
              <div style={{ display: 'grid', gap: 8 }}>
                {sections.map((section) => (
                  <div key={section.key} style={{ display: 'grid', gap: 8 }}>
                    {groupByZone ? <h3 style={{ margin: '8px 0 2px', opacity: 0.9 }}>{section.title} ({section.rows.length})</h3> : null}
                    {section.rows.map((order) => (
                      <article key={order.id} style={{ border: '1px solid rgba(255,255,255,0.22)', borderRadius: 10, padding: 10, background: 'rgba(0,0,0,0.25)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 19, fontWeight: 800 }}>
                          <span>{zoneLabel(order)}</span>
                          <span>{formatElapsed(order.created_at)}</span>
                          <span>{shortOrderId(order.id)}</span>
                        </div>
                        <div style={{ marginTop: 8, fontSize: 21, lineHeight: 1.3 }}>
                          {order.items.map((it) => <div key={it.id}><b>{it.qty}x</b> {it.name_snapshot}</div>)}
                        </div>
                        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                          {order.status === 'NEW' ? <button onClick={() => void updateStatus(order.id, 'accepted')} disabled={buttonsDisabled} style={{ fontSize: 22, padding: '8px 12px', flex: 1 }}>Accept</button> : null}
                          {order.status === 'IN_PROGRESS' ? <button onClick={() => void updateStatus(order.id, 'ready')} disabled={buttonsDisabled} style={{ fontSize: 22, padding: '8px 12px', flex: 1 }}>Ready</button> : null}
                          {order.status === 'READY' ? <button onClick={() => void updateStatus(order.id, 'completed')} disabled={buttonsDisabled} style={{ fontSize: 22, padding: '8px 12px', flex: 1 }}>Complete</button> : null}
                        </div>
                      </article>
                    ))}
                  </div>
                ))}
                {columns[col].length === 0 ? <div style={{ opacity: 0.6 }}>Aucune commande</div> : null}
              </div>
            </section>
          )
        })}
      </main>
    </div>
  )
}
