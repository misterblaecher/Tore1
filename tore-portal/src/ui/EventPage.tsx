import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout, { btn, cardStyle, inputStyle } from './Layout'
import { api } from '../utils/api'

type EventOut = {
  id: number
  name: string
  starts_at: string
  ends_at: string
  entry_price_cents: number
  ticket_mode: boolean
  ticket_value_cents: number
}

type EventDrink = {
  drink_id: number
  name: string
  type: string
  base_price_cents: number
  current_price_cents: number
  override_price_cents?: number | null
}

export default function EventPage() {
  const { eventId } = useParams()
  const id = Number(eventId)
  const [event, setEvent] = useState<EventOut | null>(null)
  const [drinks, setDrinks] = useState<EventDrink[]>([])
  const [error, setError] = useState<string | null>(null)

  // add drink
  const [dName, setDName] = useState('')
  const [dType, setDType] = useState('beer')
  const [dPrice, setDPrice] = useState('250')

  async function refresh() {
    setError(null)
    try {
      const e = await api<EventOut>(`/partner/portal/events/${id}`)
      const ds = await api<EventDrink[]>(`/partner/portal/events/${id}/drinks`)
      setEvent(e)
      setDrinks(ds)
    } catch (err: any) {
      setError(err?.message ?? 'Erreur')
    }
  }

  useEffect(() => {
    if (!Number.isFinite(id)) return
    refresh()
  }, [id])

  async function addDrink() {
    setError(null)
    try {
      await api<EventDrink>(`/partner/portal/events/${id}/drinks`, {
        method: 'POST',
        body: JSON.stringify({ name: dName, type: dType, base_price_cents: Number(dPrice), override_price_cents: null }),
      })
      setDName('')
      await refresh()
    } catch (err: any) {
      setError(err?.message ?? 'Erreur')
    }
  }

  async function deleteDrink(drinkId: number) {
    setError(null)
    try {
      await api<{ ok: boolean }>(`/partner/portal/events/${id}/drinks/${drinkId}`, { method: 'DELETE' })
      await refresh()
    } catch (err: any) {
      setError(err?.message ?? 'Erreur')
    }
  }

  return (
    <Layout title="Event">
      <div style={{ marginBottom: 12 }}>
        <Link to="/" style={{ opacity: 0.85 }}>
          ← Retour
        </Link>
      </div>

      {error && <div style={{ ...cardStyle(), borderColor: 'rgba(255,120,120,0.45)' }}>{error}</div>}

      <div style={{ display: 'grid', gap: 16 }}>
        <div style={cardStyle()}>
          <h2 style={{ marginTop: 0 }}>{event ? event.name : '…'}</h2>
          {event && (
            <div style={{ opacity: 0.8 }}>
              {new Date(event.starts_at).toLocaleString()} → {new Date(event.ends_at).toLocaleString()} — Entrée:{' '}
              {(event.entry_price_cents / 100).toFixed(2)}€
            </div>
          )}
          <div style={{ marginTop: 10, display: 'flex', gap: 12 }}>
            <button onClick={refresh} style={btn('ghost')}>
              Rafraîchir
            </button>
          </div>
        </div>

        <div style={cardStyle()}>
          <h3 style={{ marginTop: 0 }}>Menu (drinks)</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: 10, alignItems: 'end' }}>
            <label>
              <div style={{ fontSize: 12, opacity: 0.85, marginBottom: 6 }}>Nom</div>
              <input value={dName} onChange={(e) => setDName(e.target.value)} style={inputStyle()} />
            </label>
            <label>
              <div style={{ fontSize: 12, opacity: 0.85, marginBottom: 6 }}>Type</div>
              <select value={dType} onChange={(e) => setDType(e.target.value)} style={inputStyle()}>
                <option value="beer">beer</option>
                <option value="shot">shot</option>
                <option value="cocktail">cocktail</option>
                <option value="soft">soft</option>
                <option value="wine">wine</option>
              </select>
            </label>
            <label>
              <div style={{ fontSize: 12, opacity: 0.85, marginBottom: 6 }}>Prix base (cents)</div>
              <input value={dPrice} onChange={(e) => setDPrice(e.target.value)} style={inputStyle()} inputMode="numeric" />
            </label>
            <button onClick={addDrink} style={btn('primary')} disabled={!dName.trim()}>
              Ajouter
            </button>
          </div>

          <div style={{ marginTop: 12, display: 'grid', gap: 8 }}>
            {drinks.map((d) => (
              <div
                key={d.drink_id}
                style={{
                  padding: 12,
                  borderRadius: 14,
                  border: '1px solid rgba(255,255,255,0.10)',
                  background: 'rgba(255,255,255,0.03)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 12,
                  alignItems: 'center',
                }}
              >
                <div>
                  <div style={{ fontWeight: 700 }}>
                    {d.name} <span style={{ opacity: 0.65, fontWeight: 500 }}>({d.type})</span>
                  </div>
                  <div style={{ fontSize: 12, opacity: 0.75 }}>
                    Base: {(d.base_price_cents / 100).toFixed(2)}€ — Courant: {(d.current_price_cents / 100).toFixed(2)}€
                    {d.override_price_cents != null ? ` — Override: ${(d.override_price_cents / 100).toFixed(2)}€` : ''}
                  </div>
                </div>
                <button onClick={() => deleteDrink(d.drink_id)} style={btn('ghost')}>
                  Supprimer
                </button>
              </div>
            ))}
            {drinks.length === 0 && <div style={{ opacity: 0.75 }}>Aucun drink sur cet event.</div>}
          </div>
        </div>
      </div>
    </Layout>
  )
}
