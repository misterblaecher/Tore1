import React, { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout, { cardStyle, inputStyle } from '../ui/Layout'
import { ApiError, api } from '../lib/api'
import { Badge, Button, InlineAlert } from '../lib/ui'

type EventState = 'LIVE' | 'PAUSE' | 'MENU_ONLY' | 'DEGRADED' | 'FROZEN' | 'CLOSED' | string

type MenuRow = {
  id: number
  name: string
  category: string
  priceTickets: number
  available: boolean
  stockStatus: 'IN' | 'LOW' | 'OUT'
  lastPriceChangeAt?: string | null
  version: number
}

type MenuResponse = {
  eventId: number
  eventState: EventState
  items: MenuRow[]
}

type NetworkMode = 'ONLINE' | 'OFFLINE' | 'DEGRADED'

export default function BarMenuAdmin() {
  const { eventId } = useParams()
  const [items, setItems] = useState<MenuRow[]>([])
  const [eventState, setEventState] = useState<EventState>('LIVE')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Record<number, boolean>>({})
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [flash, setFlash] = useState('')
  const [isOnline, setIsOnline] = useState<boolean>(typeof navigator === 'undefined' ? true : navigator.onLine)

  const networkMode = useMemo<NetworkMode>(() => {
    if (!isOnline) return 'OFFLINE'
    if (eventState === 'DEGRADED') return 'DEGRADED'
    return 'ONLINE'
  }, [isOnline, eventState])

  const writesBlocked = useMemo(() => {
    if (networkMode === 'OFFLINE') return 'OFFLINE: lecture seule'
    if (eventState === 'FROZEN' || eventState === 'CLOSED') return `State ${eventState}: writes bloquées`
    return null
  }, [networkMode, eventState])

  const load = async () => {
    if (!eventId || networkMode === 'OFFLINE') return
    setLoading(true)
    try {
      setError('')
      const data = await api<MenuResponse>(`/partner/portal/bar/events/${eventId}/menu`)
      setItems(data.items || [])
      setEventState(data.eventState || 'LIVE')
    } catch (e) {
      if (e instanceof ApiError) setError(e.message)
      else setError('Unable to load menu')
    } finally {
      setLoading(false)
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
    void load()
  }, [eventId, networkMode])

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return items
    return items.filter((row) => row.name.toLowerCase().includes(q) || row.category.toLowerCase().includes(q))
  }, [items, search])

  const selectedIds = useMemo(() => Object.keys(selected).filter((id) => selected[Number(id)]).map(Number), [selected])

  const updateItem = async (row: MenuRow, patch: Partial<MenuRow> & { priceTickets?: number }) => {
    if (!eventId || writesBlocked) return
    const idem = `menu-row-${row.id}-${Date.now()}`
    setSaving(true)
    setFlash('')
    try {
      await api(`/partner/portal/bar/events/${eventId}/menu/items/${row.id}`, {
        method: 'PUT',
        headers: { 'Idempotency-Key': idem },
        body: JSON.stringify({
          priceTickets: patch.priceTickets,
          available: patch.available,
          stockStatus: patch.stockStatus,
          expectedVersion: row.version,
        }),
      })
      await load()
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setFlash('Conflit (409): version mismatch. Rafraîchissement de la ligne.')
        await load()
      } else if (e instanceof ApiError) {
        setError(e.message)
      } else {
        setError('Write failed')
      }
    } finally {
      setSaving(false)
    }
  }

  const bulk = async (op: Record<string, unknown>) => {
    if (!eventId || writesBlocked || selectedIds.length === 0) return
    setSaving(true)
    setFlash('')
    try {
      await api(`/partner/portal/bar/events/${eventId}/menu/bulk`, {
        method: 'POST',
        headers: { 'Idempotency-Key': `menu-bulk-${Date.now()}` },
        body: JSON.stringify({ itemIds: selectedIds, op }),
      })
      await load()
    } catch (e) {
      if (e instanceof ApiError) setError(e.message)
      else setError('Bulk update failed')
    } finally {
      setSaving(false)
    }
  }

  const exportCsv = () => {
    if (!eventId) return
    window.open(`${import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'}/partner/portal/bar/events/${eventId}/menu/export.csv`, '_blank')
  }

  return (
    <Layout title="Menu Admin">
      {writesBlocked ? <InlineAlert tone="warning">{writesBlocked}</InlineAlert> : null}
      {networkMode === 'DEGRADED' ? <InlineAlert tone="warning">DEGRADED: price changes bloqués, stock/availability autorisés.</InlineAlert> : null}
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {flash ? <InlineAlert tone="warning">{flash}</InlineAlert> : null}

      <section style={{ ...cardStyle(), marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <strong>BAR MODE · Menu Admin</strong>
            <Badge label={`EVENT ${eventId || '-'}`} tone="neutral" />
            <Badge label={`STATE ${eventState}`} tone={eventState === 'LIVE' ? 'success' : 'warning'} />
            <Badge label={`NET ${networkMode}`} tone={networkMode === 'ONLINE' ? 'success' : 'warning'} />
            {eventId ? <Link to={`/bar/events/${eventId}/dashboard`}>Dashboard</Link> : null}
            {eventId ? <Link to={`/bar/events/${eventId}/orders`}>Orders Live</Link> : null}
            {eventId ? <Link to={`/bar/events/${eventId}/analytics`}>Analytics</Link> : null}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button onClick={() => void load()} disabled={!eventId || networkMode === 'OFFLINE'}>Refresh</Button>
            <Button onClick={exportCsv} disabled={!eventId}>Export CSV</Button>
          </div>
        </div>
        <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input value={search} onChange={(e) => setSearch(e.target.value)} style={{ ...inputStyle(), minWidth: 220 }} placeholder="Search drink/category" />
        </div>
      </section>

      <section style={{ ...cardStyle(), marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <strong>Bulk ({selectedIds.length})</strong>
          <button disabled={saving || selectedIds.length === 0 || !!writesBlocked} onClick={() => void bulk({ setAvailable: true })}>Available ON</button>
          <button disabled={saving || selectedIds.length === 0 || !!writesBlocked} onClick={() => void bulk({ setAvailable: false })}>Available OFF</button>
          <button disabled={saving || selectedIds.length === 0 || !!writesBlocked} onClick={() => void bulk({ setStockStatus: 'IN' })}>Stock IN</button>
          <button disabled={saving || selectedIds.length === 0 || !!writesBlocked} onClick={() => void bulk({ setStockStatus: 'LOW' })}>Stock LOW</button>
          <button disabled={saving || selectedIds.length === 0 || !!writesBlocked} onClick={() => void bulk({ setStockStatus: 'OUT' })}>Stock OUT</button>
          <button disabled={saving || selectedIds.length === 0 || !!writesBlocked || networkMode === 'DEGRADED'} onClick={() => void bulk({ priceDeltaPct: 10 })}>Price +10%</button>
          <button disabled={saving || selectedIds.length === 0 || !!writesBlocked || networkMode === 'DEGRADED'} onClick={() => void bulk({ priceDeltaPct: -10 })}>Price -10%</button>
        </div>
      </section>

      <section style={{ ...cardStyle(), overflowX: 'auto' }}>
        {loading ? <div>Loading…</div> : null}
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th align="left">Sel</th>
              <th align="left">Name</th>
              <th align="left">Category</th>
              <th align="left">Price (tickets)</th>
              <th align="left">Stock</th>
              <th align="left">Available</th>
              <th align="left">Last change</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.id}>
                <td><input type="checkbox" checked={!!selected[row.id]} onChange={(e) => setSelected((prev) => ({ ...prev, [row.id]: e.target.checked }))} /></td>
                <td>{row.name}</td>
                <td>{row.category}</td>
                <td>
                  <input
                    type="number"
                    defaultValue={row.priceTickets}
                    style={{ ...inputStyle(), width: 90 }}
                    disabled={!!writesBlocked || saving || networkMode === 'DEGRADED'}
                    onBlur={(e) => {
                      const next = Number(e.target.value || 0)
                      if (next !== row.priceTickets) void updateItem(row, { priceTickets: next })
                    }}
                  />
                </td>
                <td>
                  <select
                    value={row.stockStatus}
                    disabled={!!writesBlocked || saving}
                    onChange={(e) => void updateItem(row, { stockStatus: e.target.value as MenuRow['stockStatus'] })}
                  >
                    <option value="IN">IN</option>
                    <option value="LOW">LOW</option>
                    <option value="OUT">OUT</option>
                  </select>
                </td>
                <td>
                  <button disabled={!!writesBlocked || saving} onClick={() => void updateItem(row, { available: !row.available })}>
                    {row.available ? 'ON' : 'OFF'}
                  </button>
                </td>
                <td>{row.lastPriceChangeAt ? new Date(row.lastPriceChangeAt).toLocaleTimeString() : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </Layout>
  )
}
