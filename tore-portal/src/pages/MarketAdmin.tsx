import React, { useEffect, useMemo, useState } from 'react'
import Layout, { btn, cardStyle, inputStyle } from '../ui/Layout'
import { api, API_BASE } from '../lib/api'
import { getSession } from '../lib/auth'

type MarketConfig = {
  id: number
  bar_id: number
  event_id: number | null
  is_live: boolean
  price_floor_cents: number
  price_cap_cents: number
  step_cents: number
  updated_at: string
}

type MarketItem = {
  id: number
  name: string
  current_price_cents: number
  base_price_cents: number
  unit: string
  is_active: boolean
  sort_order: number
}

export default function MarketAdmin() {
  const session = getSession()
  const barId = session?.bar_id
  const [eventIdRaw, setEventIdRaw] = useState('')
  const [isLive, setIsLive] = useState(false)
  const [config, setConfig] = useState<MarketConfig | null>(null)
  const [items, setItems] = useState<MarketItem[]>([])
  const [newName, setNewName] = useState('')
  const [newPrice, setNewPrice] = useState(250)
  const [error, setError] = useState<string | null>(null)

  const eventId = eventIdRaw.trim() ? Number(eventIdRaw) : null

  const load = async () => {
    try {
      setError(null)
      const query = eventId ? `?event_id=${eventId}` : ''
      const cfg = await api<MarketConfig>(`/partner/portal/market/config${query}`)
      setConfig(cfg)
      setIsLive(cfg.is_live)
      const rows = await api<MarketItem[]>(`/partner/portal/market/items${query}`)
      setItems(rows)
    } catch (e: any) {
      setConfig(null)
      setItems([])
      setError(e?.message || 'Impossible de charger le market')
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventIdRaw])

  const upsertConfig = async () => {
    const body: Record<string, unknown> = { is_live: isLive }
    if (eventId) body.event_id = eventId
    await api('/partner/portal/market/config', { method: 'POST', body: JSON.stringify(body) })
    await load()
  }

  const createItem = async () => {
    if (!newName.trim()) return
    const body: Record<string, unknown> = { name: newName.trim(), base_price_cents: Number(newPrice || 0), unit: 'unit', sort_order: items.length + 1 }
    if (eventId) body.event_id = eventId
    await api('/partner/portal/market/items', { method: 'POST', body: JSON.stringify(body) })
    setNewName('')
    setNewPrice(250)
    await load()
  }

  const patchItem = async (id: number, patch: Record<string, unknown>) => {
    await api(`/partner/portal/market/items/${id}`, { method: 'PATCH', body: JSON.stringify(patch) })
    await load()
  }

  const setPrice = async (item: MarketItem, price: number) => {
    await api(`/partner/portal/market/items/${item.id}/price`, { method: 'POST', body: JSON.stringify({ price_cents: Number(price || 0) }) })
    await load()
  }

  const publicUrl = useMemo(() => {
    if (!barId) return ''
    const query = eventId ? `&event_id=${eventId}` : ''
    return `${API_BASE}/market/public?bar_id=${barId}${query}`
  }, [barId, eventId])

  const deepLink = useMemo(() => {
    if (!barId) return ''
    const query = eventId ? `&event_id=${eventId}` : ''
    return `tore://market?bar_id=${barId}${query}`
  }, [barId, eventId])

  return (
    <Layout title="Market admin">
      {error ? <div style={{ color: '#ffb4b4', fontWeight: 700 }}>{error}</div> : null}
      <div style={{ ...cardStyle(), display: 'grid', gap: 10 }}>
        <input style={inputStyle()} type="number" placeholder="event_id (optionnel)" value={eventIdRaw} onChange={(e) => setEventIdRaw(e.target.value)} />
        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" checked={isLive} onChange={(e) => setIsLive(e.target.checked)} />
          Market live
        </label>
        <button style={btn()} onClick={upsertConfig}>Create / Update config</button>
      </div>

      <div style={{ ...cardStyle(), marginTop: 12, display: 'grid', gap: 8 }}>
        <div>Public URL: {publicUrl || '-'}</div>
        <div>Deep link: {deepLink || '-'}</div>
      </div>

      <div style={{ ...cardStyle(), marginTop: 12, display: 'flex', gap: 8 }}>
        <input style={inputStyle()} placeholder="Nom item" value={newName} onChange={(e) => setNewName(e.target.value)} />
        <input style={{ ...inputStyle(), maxWidth: 130 }} type="number" value={newPrice} onChange={(e) => setNewPrice(Number(e.target.value || 0))} />
        <button style={btn()} onClick={createItem}>Ajouter item</button>
      </div>

      <div style={{ marginTop: 12, display: 'grid', gap: 8 }}>
        {items.map((item) => (
          <MarketItemRow key={item.id} item={item} onPatch={patchItem} onSetPrice={setPrice} />
        ))}
      </div>
      {config ? <div style={{ marginTop: 10, opacity: 0.75 }}>Config #{config.id} mise à jour: {new Date(config.updated_at).toLocaleString()}</div> : null}
    </Layout>
  )
}

function MarketItemRow({ item, onPatch, onSetPrice }: { item: MarketItem; onPatch: (id: number, patch: Record<string, unknown>) => Promise<void>; onSetPrice: (item: MarketItem, price: number) => Promise<void> }) {
  const [priceInput, setPriceInput] = useState(item.current_price_cents)
  const [sortInput, setSortInput] = useState(item.sort_order)

  useEffect(() => {
    setPriceInput(item.current_price_cents)
    setSortInput(item.sort_order)
  }, [item.current_price_cents, item.sort_order])

  return (
    <div style={{ ...cardStyle(), display: 'grid', gap: 8 }}>
      <div style={{ fontWeight: 700 }}>{item.name}</div>
      <div>Price: {item.current_price_cents} cts | Base: {item.base_price_cents} cts</div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button style={btn('ghost')} onClick={() => onPatch(item.id, { is_active: !item.is_active })}>active: {item.is_active ? 'ON' : 'OFF'}</button>
        <input style={{ ...inputStyle(), maxWidth: 110 }} type="number" value={sortInput} onChange={(e) => setSortInput(Number(e.target.value || 0))} />
        <button style={btn('ghost')} onClick={() => onPatch(item.id, { sort_order: sortInput })}>Set sort</button>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <input style={{ ...inputStyle(), maxWidth: 130 }} type="number" value={priceInput} onChange={(e) => setPriceInput(Number(e.target.value || 0))} />
        <button style={btn()} onClick={() => onSetPrice(item, priceInput)}>Set price</button>
      </div>
    </div>
  )
}
