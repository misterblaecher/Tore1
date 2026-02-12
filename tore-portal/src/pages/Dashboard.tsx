import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api, API_BASE, ApiError } from '../lib/api'
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
  ticket_mode?: boolean
  ticket_value_cents?: number
  tickets_enabled?: boolean
  entry_enabled?: boolean
}

type EntryStatsOut = {
  total: number
  last_hour: number
}

export default function Dashboard() {
  const [bar, setBar] = useState<BarOut | null>(null)
  const [events, setEvents] = useState<EventOut[]>([])
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null)
  const [stats, setStats] = useState<EntryStatsOut | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [statsError, setStatsError] = useState<string | null>(null)
  const [loadingEvents, setLoadingEvents] = useState(false)
  const [loadingStats, setLoadingStats] = useState(false)
  const [apiDown, setApiDown] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const now = useMemo(() => new Date(), [])

  useEffect(() => {
    ;(async () => {
      setApiDown(false)
      setLoadingEvents(true)
      try {
        setError(null)
        const b = await api<BarOut>('/partner/portal/bar')
        let ev = await api<EventOut[]>('/partner/portal/events')
        if (ev.length === 0) {
          const res = await fetch(`${API_BASE}/events`)
          if (res.ok) {
            ev = (await res.json()) as EventOut[]
          }
        }
        if (ev.length === 0) {
          const fallbackStart = new Date()
          const fallbackEnd = new Date(fallbackStart.getTime() + 4 * 3600 * 1000)
          ev = [
            {
              id: 1,
              bar_id: b.id,
              name: 'Event démo',
              starts_at: fallbackStart.toISOString(),
              ends_at: fallbackEnd.toISOString(),
              entry_price_cents: 0,
              ticket_mode: false,
              ticket_value_cents: 0,
              tickets_enabled: false,
              entry_enabled: false,
            },
          ]
          setError('Mode démo activé : événement local utilisé.')
        }
        setBar(b)
        setEvents(ev)
        setSelectedEventId((prev) => prev ?? ev[0]?.id ?? null)
      } catch (e: any) {
        if (isApiUnavailable(e)) {
          setApiDown(true)
        } else {
          setError('Impossible de charger les informations pour le moment.')
        }
      } finally {
        setLoadingEvents(false)
      }
    })()
  }, [])

  const refreshStats = useCallback(async () => {
    if (!selectedEventId) return
    setLoadingStats(true)
    setStatsError(null)
    try {
      const data = await api<EntryStatsOut>(`/events/${selectedEventId}/entry/stats`)
      setStats(data)
      setLastUpdated(new Date())
    } catch (e: any) {
      if (isApiUnavailable(e)) {
        setApiDown(true)
      } else {
        if (e instanceof ApiError) {
          const statusLabel = e.status ? `HTTP ${e.status}` : 'Erreur'
          const message = e.message || 'Erreur inconnue'
          setStatsError(`${statusLabel} — ${message}`)
          if (e.url) {
            console.error('[Stats entrée] Erreur API', { url: e.url, status: e.status, message })
          } else {
            console.error('[Stats entrée] Erreur API', { status: e.status, message })
          }
        } else {
          setStatsError('Impossible de charger les stats pour cet événement.')
          console.error('[Stats entrée] Erreur inconnue', e)
        }
      }
    } finally {
      setLoadingStats(false)
    }
  }, [selectedEventId])

  useEffect(() => {
    if (!selectedEventId) return
    refreshStats()
    const interval = window.setInterval(() => {
      refreshStats()
    }, 10000)
    return () => window.clearInterval(interval)
  }, [refreshStats, selectedEventId])

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

      {loadingEvents ? (
        <div style={{ opacity: 0.8 }}>Chargement des informations…</div>
      ) : null}

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

      <div style={{ marginTop: 16, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <Link
          to="/polymarket"
          style={{
            display: 'inline-block',
            padding: '10px 14px',
            borderRadius: 12,
            border: '1px solid rgba(255,0,160,0.4)',
            background: 'rgba(255,0,160,0.25)',
            color: '#fff',
            fontWeight: 800,
            textDecoration: 'none',
          }}
        >
          Ouvrir Polymarket Global
        </Link>
        <Link
          to="/analytics"
          style={{
            display: 'inline-block',
            padding: '10px 14px',
            borderRadius: 12,
            border: '1px solid rgba(255,210,0,0.4)',
            background: 'rgba(255,210,0,0.2)',
            color: '#fff',
            fontWeight: 800,
            textDecoration: 'none',
          }}
        >
          Ops Analytics
        </Link>
        <Link
          to="/orders-queue"
          style={{
            display: 'inline-block',
            padding: '10px 14px',
            borderRadius: 12,
            border: '1px solid rgba(0,255,180,0.35)',
            background: 'rgba(0,255,180,0.18)',
            color: '#fff',
            fontWeight: 800,
            textDecoration: 'none',
          }}
        >
          Orders Queue
        </Link>
        <Link
          to="/menu-admin"
          style={{
            display: 'inline-block',
            padding: '10px 14px',
            borderRadius: 12,
            border: '1px solid rgba(255,255,255,0.3)',
            background: 'rgba(255,255,255,0.1)',
            color: '#fff',
            fontWeight: 800,
            textDecoration: 'none',
          }}
        >
          Gérer Menu QR
        </Link>
        {bar ? (
          <Link
            to={`/menu/${bar.id}`}
            style={{
              display: 'inline-block',
              padding: '10px 14px',
              borderRadius: 12,
              border: '1px solid rgba(0,180,255,0.45)',
              background: 'rgba(0,180,255,0.25)',
              color: '#fff',
              fontWeight: 800,
              textDecoration: 'none',
            }}
          >
            Ouvrir Menu Public
          </Link>
        ) : null}
      </div>

      <h2 style={{ marginTop: 22 }}>Événements</h2>
      <div style={{ display: 'grid', gap: 12 }}>
        <label style={{ display: 'grid', gap: 6 }}>
          <span style={{ opacity: 0.8 }}>Sélectionner un événement</span>
          <select
            value={selectedEventId ?? ''}
            onChange={(e) => setSelectedEventId(e.target.value ? Number(e.target.value) : null)}
            style={{
              padding: 10,
              borderRadius: 10,
              border: '1px solid rgba(255,255,255,0.18)',
              background: 'transparent',
              color: '#fff',
            }}
          >
            {events.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name}
              </option>
            ))}
          </select>
        </label>

        {events.map((e) => {
          const starts = new Date(e.starts_at)
          const isPast = starts.getTime() < now.getTime() - 24 * 3600 * 1000
          const ticketsEnabled = e.tickets_enabled ?? e.ticket_mode ?? false
          const entryEnabled = e.entry_enabled ?? false
          return (
            <div
              key={e.id}
              style={{
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
                Entrée: {entryEnabled ? 'ON' : 'OFF'} ({(e.entry_price_cents / 100).toFixed(2)}€) —{' '}
                {ticketsEnabled ? 'Tickets ON' : 'Tickets OFF'}
              </div>
            </div>
          )
        })}

        {!loadingEvents && events.length === 0 ? <div style={{ opacity: 0.75 }}>Aucun event pour l’instant.</div> : null}
      </div>

      <h2 style={{ marginTop: 24 }}>Stats Entrée</h2>
      <div
        style={{
          border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 16,
          padding: 16,
          background: 'rgba(255,255,255,0.04)',
          display: 'grid',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div style={{ opacity: 0.8 }}>
            {lastUpdated ? `Mis à jour à ${lastUpdated.toLocaleTimeString()}` : 'Pas encore chargé.'}
          </div>
          <button
            type="button"
            onClick={() => refreshStats()}
            disabled={loadingStats || !selectedEventId}
            style={{
              padding: '8px 12px',
              borderRadius: 12,
              border: '1px solid rgba(255,255,255,0.18)',
              background: '#ffffff',
              color: '#000',
              fontWeight: 800,
              cursor: 'pointer',
            }}
          >
            {loadingStats ? 'Actualisation…' : 'Refresh'}
          </button>
        </div>

        {statsError ? <div style={{ color: '#ffb4b4', fontWeight: 700 }}>{statsError}</div> : null}

        {loadingStats ? (
          <div style={{ opacity: 0.8 }}>Chargement des stats…</div>
        ) : stats ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
            <div style={{ border: '1px solid rgba(255,255,255,0.12)', borderRadius: 14, padding: 12 }}>
              <div style={{ opacity: 0.7 }}>Total</div>
              <div style={{ fontSize: 24, fontWeight: 800 }}>{stats.total}</div>
            </div>
            <div style={{ border: '1px solid rgba(255,255,255,0.12)', borderRadius: 14, padding: 12 }}>
              <div style={{ opacity: 0.7 }}>Dernière heure</div>
              <div style={{ fontSize: 24, fontWeight: 800 }}>{stats.last_hour}</div>
            </div>
          </div>
        ) : (
          <div style={{ opacity: 0.7 }}>Sélectionne un événement pour voir les stats.</div>
        )}
      </div>
    </Layout>
  )
}
