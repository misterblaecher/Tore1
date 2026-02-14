import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { API_BASE } from '../lib/api'

type PublicConfig = {
  is_live: boolean
}

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
  source?: string
  ref_order_id?: number
}

type PublicPayload = {
  config: PublicConfig
  items: PublicItem[]
  ticker: PublicTick[]
}

type LiveStatus = 'LIVE' | 'RECONNECTING' | 'OFFLINE'

export default function MarketPublic() {
  const { barId } = useParams()
  const [searchParams] = useSearchParams()
  const eventId = searchParams.get('event_id')
  const [data, setData] = useState<PublicPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [liveEnabled, setLiveEnabled] = useState(false)
  const [liveStatus, setLiveStatus] = useState<LiveStatus>('OFFLINE')
  const reconnectTimeoutRef = useRef<number | null>(null)

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
        setLiveEnabled(Boolean(payload?.config?.is_live))
      } catch (e: any) {
        setError(e?.message || 'Impossible de charger le market public')
      }
    })()
  }, [query])

  useEffect(() => {
    if (!liveEnabled) {
      setLiveStatus('OFFLINE')
      return
    }

    let isStopped = false
    let source: EventSource | null = null
    let fallbackInterval: number | null = null

    const startFallbackPolling = () => {
      if (fallbackInterval !== null) return
      fallbackInterval = window.setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/market/public?${query}`)
          const payload = await res.json()
          if (!res.ok) return
          setData(payload)
          setLiveStatus('RECONNECTING')
        } catch {
          setLiveStatus('OFFLINE')
        }
      }, 5000)
    }

    const connect = () => {
      if (isStopped) return
      setLiveStatus('RECONNECTING')
      source = new EventSource(`${API_BASE}/market/public/stream?${query}`)

      source.addEventListener('tick', (event) => {
        try {
          const tick = JSON.parse((event as MessageEvent).data) as PublicTick
          setData((current) => {
            if (!current) return current
            return {
              ...current,
              items: current.items.map((item) =>
                item.id === tick.item_id ? { ...item, current_price_cents: tick.price_cents } : item,
              ),
              ticker: [tick, ...current.ticker].slice(0, 30),
            }
          })
          setLiveStatus('LIVE')
        } catch {
          setLiveStatus('RECONNECTING')
        }
      })

      source.onerror = () => {
        if (source) {
          source.close()
          source = null
        }
        setLiveStatus('RECONNECTING')
        startFallbackPolling()
        if (reconnectTimeoutRef.current !== null) {
          window.clearTimeout(reconnectTimeoutRef.current)
        }
        reconnectTimeoutRef.current = window.setTimeout(connect, 3000)
      }
    }

    connect()

    return () => {
      isStopped = true
      if (source) source.close()
      if (fallbackInterval !== null) window.clearInterval(fallbackInterval)
      if (reconnectTimeoutRef.current !== null) {
        window.clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
    }
  }, [liveEnabled, query])

  return (
    <div style={{ maxWidth: 740, margin: '20px auto', color: '#fff', fontFamily: 'Inter, sans-serif' }}>
      <h1>Market boissons</h1>
      {error ? <div style={{ color: '#ff9f9f' }}>{error}</div> : null}
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 12 }}>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" checked={liveEnabled} onChange={(e) => setLiveEnabled(e.target.checked)} />
          Live
        </label>
        <strong>{liveStatus}</strong>
      </div>

      <div style={{ display: 'grid', gap: 10 }}>
        {(data?.items || []).map((item) => (
          <div key={item.id} style={{ border: '1px solid rgba(255,255,255,0.2)', padding: 12, borderRadius: 10, opacity: item.is_active ? 1 : 0.6 }}>
            <div style={{ fontWeight: 800 }}>{item.name}</div>
            <div>
              {item.current_price_cents} cts ({item.unit})
            </div>
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
