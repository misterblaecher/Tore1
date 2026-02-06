import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout, { btn, cardStyle, inputStyle } from './Layout'
import { api } from '../utils/api'

type BarOut = { id: number; name: string; city: string; lat?: number | null; lng?: number | null }
type EventOut = {
  id: number
  bar_id: number
  name: string
  starts_at: string
  ends_at: string
  entry_price_cents: number
  ticket_mode: boolean
  ticket_value_cents: number
}

export default function DashboardPage() {
  const [bar, setBar] = useState<BarOut | null>(null)
  const [events, setEvents] = useState<EventOut[]>([])
  const [error, setError] = useState<string | null>(null)

  // create event
  const nowIso = useMemo(() => new Date().toISOString().slice(0, 16), [])
  const [evName, setEvName] = useState('')
  const [startsAt, setStartsAt] = useState(nowIso)
  const [endsAt, setEndsAt] = useState(nowIso)
  const [entry, setEntry] = useState('0')

  async function refresh() {
    setError(null)
    try {
      const b = await api<BarOut>('/partner/portal/bar')
      const e = await api<EventOut[]>('/partner/portal/events')
      setBar(b)
      setEvents(e)
    } catch (err: any) {
      setError(err?.message ?? 'Erreur')
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  async function createEvent() {
    setError(null)
    try {
      const payload = {
        name: evName,
        starts_at: new Date(startsAt).toISOString(),
        ends_at: new Date(endsAt).toISOString(),
        entry_price_cents: Number(entry),
        ticket_mode: true,
        ticket_value_cents: 200,
      }
      await api<EventOut>('/partner/portal/events', { method: 'POST', body: JSON.stringify(payload) })
      setEvName('')
      await refresh()
    } catch (err: any) {
      setError(err?.message ?? 'Erreur')
    }
  }

  return (
    <Layout title="Dashboard">
      {error && <div style={{ ...cardStyle(), borderColor: 'rgba(255,120,120,0.45)' }}>{error}</div>}

      <div style={{ display: 'grid', gap: 16 }}>
        <div style={cardStyle()}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <h2 style={{ margin: 0 }}>{bar ? bar.name : '…'}</h2>
            {bar && <div style={{ opacity: 0.75 }}>{bar.city} — Bar #{bar.id}</div>}
          </div>
          <div style={{ opacity: 0.75, marginTop: 8 }}>
            MVP portail : gérer events + menu (drinks) + exports basiques.
          </div>
        </div>

        <div style={cardStyle()}>
          <h3 style={{ marginTop: 0 }}>Créer un event (manager)</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <label>
              <div style={{ fontSize: 12, opacity: 0.85, marginBottom: 6 }}>Nom</div>
              <input value={evName} onChange={(e) => setEvName(e.target.value)} style={inputStyle()} placeholder="Soirée TORÈ" />
            </label>
            <label>
              <div style={{ fontSize: 12, opacity: 0.85, marginBottom: 6 }}>Entrée (cents)</div>
              <input value={entry} onChange={(e) => setEntry(e.target.value)} style={inputStyle()} inputMode="numeric" />
            </label>
            <label>
              <div style={{ fontSize: 12, opacity: 0.85, marginBottom: 6 }}>Début</div>
              <input type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} style={inputStyle()} />
            </label>
            <label>
              <div style={{ fontSize: 12, opacity: 0.85, marginBottom: 6 }}>Fin</div>
              <input type="datetime-local" value={endsAt} onChange={(e) => setEndsAt(e.target.value)} style={inputStyle()} />
            </label>
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 12 }}>
            <button onClick={createEvent} style={btn('primary')} disabled={!evName.trim()}>
              Créer
            </button>
            <button onClick={refresh} style={btn('ghost')}>
              Rafraîchir
            </button>
          </div>
        </div>

        <div style={cardStyle()}>
          <h3 style={{ marginTop: 0 }}>Events</h3>
          <div style={{ display: 'grid', gap: 10 }}>
            {events.map((e) => (
              <Link key={e.id} to={`/events/${e.id}`} style={{ textDecoration: 'none' }}>
                <div
                  style={{
                    padding: 12,
                    borderRadius: 14,
                    border: '1px solid rgba(255,255,255,0.10)',
                    background: 'rgba(255,255,255,0.03)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: 12,
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 700 }}>{e.name}</div>
                    <div style={{ fontSize: 12, opacity: 0.75 }}>
                      {new Date(e.starts_at).toLocaleString()} → {new Date(e.ends_at).toLocaleString()}
                    </div>
                  </div>
                  <div style={{ fontSize: 12, opacity: 0.8, textAlign: 'right' }}>
                    Entrée: {(e.entry_price_cents / 100).toFixed(2)}€
                  </div>
                </div>
              </Link>
            ))}
            {events.length === 0 && <div style={{ opacity: 0.75 }}>Aucun event.</div>}
          </div>
        </div>
      </div>
    </Layout>
  )
}
