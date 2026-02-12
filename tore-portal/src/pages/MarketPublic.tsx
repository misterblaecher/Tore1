import React, { useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { API_BASE } from '../lib/api'

type PublicItem = {
  id: number
  name: string
  current_price_cents: number
  base_price_cents: number
  unit: string
  is_active: boolean
}

type PublicTick = {
  item_id: number
  price_cents: number
  ts: string
}

type PublicPayload = {
  items: PublicItem[]
  ticker: PublicTick[]
}

export default function MarketPublic() {
  const { barId } = useParams()
  const [searchParams] = useSearchParams()
  const eventId = searchParams.get('event_id')
  const [data, setData] = useState<PublicPayload | null>(null)
  const [error, setError] = useState<string | null>(null)

  const query = useMemo(() => {
    const parts = [`bar_id=${barId}`]
    if (eventId) parts.push(`event_id=${eventId}`)
    return parts.join('&')
  }, [barId, eventId])

  useEffect(() => {
    ;(async () => {
      try {
        setError(null)
        const res = await fetch(`${API_BASE}/market/public?${query}`)
        const payload = await res.json()
        if (!res.ok) throw new Error(payload?.detail || `HTTP ${res.status}`)
        setData(payload)
      } catch (e: any) {
        setError(e?.message || 'Impossible de charger le market public')
      }
    })()
  }, [query])

  return (
    <div style={{ maxWidth: 740, margin: '20px auto', color: '#fff', fontFamily: 'Inter, sans-serif' }}>
      <h1>Market boissons</h1>
      {error ? <div style={{ color: '#ff9f9f' }}>{error}</div> : null}
      <div style={{ display: 'grid', gap: 10 }}>
        {(data?.items || []).map((item) => (
          <div key={item.id} style={{ border: '1px solid rgba(255,255,255,0.2)', padding: 12, borderRadius: 10, opacity: item.is_active ? 1 : 0.6 }}>
            <div style={{ fontWeight: 800 }}>{item.name}</div>
            <div>{item.current_price_cents} cts ({item.unit})</div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 20 }}>
        <h3>Ticker live</h3>
        <div style={{ display: 'grid', gap: 6 }}>
          {(data?.ticker || []).map((tick, idx) => (
            <div key={`${tick.item_id}-${tick.ts}-${idx}`} style={{ opacity: 0.9 }}>
              item #{tick.item_id} → {tick.price_cents} cts · {new Date(tick.ts).toLocaleTimeString()}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
