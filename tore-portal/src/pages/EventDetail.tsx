import React, { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'

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

type EventDrinkOut = {
  drink_id: number
  name: string
  type: string
  base_price_cents: number
  current_price_cents: number
  override_price_cents: number | null
}

export default function EventDetail() {
  const { eventId } = useParams()
  const id = Number(eventId)

  const [event, setEvent] = useState<EventOut | null>(null)
  const [drinks, setDrinks] = useState<EventDrinkOut[]>([])
  const [error, setError] = useState<string | null>(null)
  const [adding, setAdding] = useState({ name: '', type: 'beer', base_price_cents: 250 })

  const grouped = useMemo(() => {
    const m = new Map<string, EventDrinkOut[]>()
    for (const d of drinks) {
      const arr = m.get(d.type) ?? []
      arr.push(d)
      m.set(d.type, arr)
    }
    return Array.from(m.entries()).sort((a, b) => a[0].localeCompare(b[0]))
  }, [drinks])

  async function load() {
    try {
      setError(null)
      const e = await api<EventOut>(`/partner/portal/events/${id}`)
      const d = await api<EventDrinkOut[]>(`/partner/portal/events/${id}/drinks`)
      setEvent(e)
      setDrinks(d)
    } catch (e: any) {
      setError(e?.message ?? 'Erreur')
    }
  }

  useEffect(() => {
    if (!Number.isFinite(id)) return
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  async function addDrink(e: React.FormEvent) {
    e.preventDefault()
    try {
      setError(null)
      await api<EventDrinkOut>(`/partner/portal/events/${id}/drinks`, {
        method: 'POST',
        body: JSON.stringify({
          name: adding.name,
          type: adding.type,
          base_price_cents: adding.base_price_cents,
          override_price_cents: null,
        }),
      })
      setAdding({ name: '', type: adding.type, base_price_cents: adding.base_price_cents })
      await load()
    } catch (e: any) {
      setError(e?.message ?? 'Erreur')
    }
  }

  async function removeDrink(drink_id: number) {
    if (!confirm('Supprimer cet item de l’event ?')) return
    try {
      setError(null)
      await api<{ ok: true }>(`/partner/portal/events/${id}/drinks/${drink_id}`, { method: 'DELETE' })
      await load()
    } catch (e: any) {
      setError(e?.message ?? 'Erreur')
    }
  }

  return (
    <Layout title="Event">
      {error ? <div style={{ color: '#ffb4b4', fontWeight: 700 }}>{error}</div> : null}

      {event ? (
        <div
          style={{
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: 16,
            padding: 16,
            background: 'rgba(255,255,255,0.04)',
          }}
        >
          <div style={{ fontSize: 22, fontWeight: 900 }}>{event.name}</div>
          <div style={{ opacity: 0.85, marginTop: 6 }}>
            {new Date(event.starts_at).toLocaleString()} → {new Date(event.ends_at).toLocaleString()}
          </div>
        </div>
      ) : null}

      <h2 style={{ marginTop: 22 }}>Menu (drinks)</h2>

      <form
        onSubmit={addDrink}
        style={{
          display: 'grid',
          gridTemplateColumns: '2fr 1fr 1fr auto',
          gap: 10,
          alignItems: 'end',
          border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 16,
          padding: 16,
          background: 'rgba(255,255,255,0.04)',
        }}
      >
        <label style={{ display: 'grid', gap: 6 }}>
          <span style={{ opacity: 0.85 }}>Nom</span>
          <input
            value={adding.name}
            onChange={(e) => setAdding((p) => ({ ...p, name: e.target.value }))}
            required
            style={{ padding: 10, borderRadius: 10, border: '1px solid rgba(255,255,255,0.18)', background: 'transparent', color: '#fff' }}
          />
        </label>
        <label style={{ display: 'grid', gap: 6 }}>
          <span style={{ opacity: 0.85 }}>Type</span>
          <select
            value={adding.type}
            onChange={(e) => setAdding((p) => ({ ...p, type: e.target.value }))}
            style={{ padding: 10, borderRadius: 10, border: '1px solid rgba(255,255,255,0.18)', background: 'transparent', color: '#fff' }}
          >
            <option value="beer">beer</option>
            <option value="shot">shot</option>
            <option value="cocktail">cocktail</option>
            <option value="soft">soft</option>
            <option value="other">other</option>
          </select>
        </label>
        <label style={{ display: 'grid', gap: 6 }}>
          <span style={{ opacity: 0.85 }}>Prix base (€)</span>
          <input
            type="number"
            value={(adding.base_price_cents / 100).toString()}
            step="0.01"
            min="0"
            onChange={(e) => setAdding((p) => ({ ...p, base_price_cents: Math.round(Number(e.target.value) * 100) }))}
            style={{ padding: 10, borderRadius: 10, border: '1px solid rgba(255,255,255,0.18)', background: 'transparent', color: '#fff' }}
          />
        </label>
        <button
          type="submit"
          style={{
            padding: '10px 12px',
            borderRadius: 12,
            border: '1px solid rgba(255,255,255,0.18)',
            background: '#ffffff',
            color: '#000',
            fontWeight: 800,
            cursor: 'pointer',
          }}
        >
          Ajouter
        </button>
      </form>

      <div style={{ marginTop: 14, display: 'grid', gap: 16 }}>
        {grouped.map(([type, items]) => (
          <div key={type}>
            <div style={{ fontWeight: 900, textTransform: 'uppercase', opacity: 0.8, letterSpacing: 0.6 }}>{type}</div>
            <div style={{ display: 'grid', gap: 10, marginTop: 8 }}>
              {items.map((d) => (
                <div
                  key={d.drink_id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 10,
                    border: '1px solid rgba(255,255,255,0.12)',
                    borderRadius: 16,
                    padding: 14,
                    background: 'rgba(255,255,255,0.04)',
                  }}
                >
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 800 }}>{d.name}</div>
                    <div style={{ opacity: 0.85 }}>
                      Base: {(d.base_price_cents / 100).toFixed(2)}€ — Actuel: {(d.current_price_cents / 100).toFixed(2)}€
                      {d.override_price_cents != null ? ` — Override: ${(d.override_price_cents / 100).toFixed(2)}€` : ''}
                    </div>
                  </div>
                  <button
                    onClick={() => removeDrink(d.drink_id)}
                    style={{
                      border: '1px solid rgba(255,255,255,0.18)',
                      background: 'transparent',
                      color: '#fff',
                      padding: '8px 10px',
                      borderRadius: 10,
                      cursor: 'pointer',
                    }}
                  >
                    Supprimer
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}

        {drinks.length === 0 ? <div style={{ opacity: 0.75 }}>Aucun item pour cet event.</div> : null}
      </div>
    </Layout>
  )
}
