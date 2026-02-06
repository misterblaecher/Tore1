import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'
import { isApiUnavailable } from '../lib/errors'
import ApiUnavailable from '../ui/ApiUnavailable'

type BarOut = {
  id: number
  name: string
  city: string
  lat?: number | null
  lng?: number | null
}

type EventOut = {
  id: number
  bar_id: number | null
  name: string
  starts_at: string
  ends_at: string
  entry_price_cents: number
  ticket_mode: boolean
  ticket_value_cents: number
}

export default function Dashboard() {
  const [bar, setBar] = useState<BarOut | null>(null)
  const [events, setEvents] = useState<EventOut[]>([])
  const [error, setError] = useState<string | null>(null)

  const now = useMemo(() => new Date(), [])

  useEffect(() => {
    ;(async () => {
      try {
        setError(null)
        const b = await api<BarOut>('/partner/portal/bar')
        const ev = await api<EventOut[]>('/partner/portal/events')
        setBar(b)
        setEvents(ev)
      } catch (e: any) {
        setError(e?.message ?? 'Erreur')
      }
    })()
  }, [])

  const apiDown = error ? isApiUnavailable(new Error(error)) : false

  if (apiDown) {
    return (
      <Layout title="Dashboard">
        <ApiUnavailable />
      </Layout>
    )
  }

  return (
    <Layout title="Dashboard">
      {error ? <div style={{ color: '#ffb4b4', fontWeight: 700 }}>{error}</div> : null}

      {bar ? (
        <div
          style={{
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: 16,
            padding: 16,
            background: 'rgba(255,255,255,0.04)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: 22, fontWeight: 900 }}>{bar.name}</div>
              <div style={{ opacity: 0.8 }}>{bar.city}</div>
            </div>
            <div style={{ opacity: 0.75 }}>Bar #{bar.id}</div>
          </div>
        </div>
      ) : null}

      <h2 style={{ marginTop: 22 }}>Événements</h2>
      <div style={{ display: 'grid', gap: 12 }}>
        {events.map((e) => {
          const starts = new Date(e.starts_at)
          const isPast = starts.getTime() < now.getTime() - 24 * 3600 * 1000
          return (
            <Link
              key={e.id}
              to={`/events/${e.id}`}
              style={{
                textDecoration: 'none',
                border: '1px solid rgba(255,255,255,0.12)',
                borderRadius: 16,
                padding: 16,
                background: 'rgba(255,255,255,0.04)',
                display: 'grid',
                gap: 6,
                opacity: isPast ? 0.7 : 1,
              }}
            >
              <div style={{ fontSize: 18, fontWeight: 800 }}>{e.name}</div>
              <div style={{ opacity: 0.85 }}>
                {new Date(e.starts_at).toLocaleString()} → {new Date(e.ends_at).toLocaleString()}
              </div>
              <div style={{ opacity: 0.8 }}>
                Entrée: {(e.entry_price_cents / 100).toFixed(2)}€ — {e.ticket_mode ? 'Tickets ON' : 'Tickets OFF'}
              </div>
            </Link>
          )
        })}

        {events.length === 0 ? <div style={{ opacity: 0.75 }}>Aucun event pour l’instant.</div> : null}
      </div>
    </Layout>
  )
}
