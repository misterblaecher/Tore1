import React, { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'
import { isApiUnavailable } from '../lib/errors'
import ApiUnavailable from '../ui/ApiUnavailable'

type EventOut = {
  id: number
  bar_id: number | null
  name: string
  starts_at: string
  ends_at: string
  entry_price_cents: number
  ticket_mode?: boolean
  tickets_enabled?: boolean
  entry_enabled?: boolean
}

type EventCostOut = {
  id: number
  event_id: number
  label: string
  amount_cents: number
  category: string
  created_at?: string
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
  const [settings, setSettings] = useState({
    name: '',
    tickets_enabled: false,
    entry_enabled: false,
    entry_price_cents: 0,
  })
  const [settingsStatus, setSettingsStatus] = useState<{ ok: boolean; message: string } | null>(null)
  const [costs, setCosts] = useState<EventCostOut[]>([])
  const [costInput, setCostInput] = useState({ label: '', amount_cents: 0, category: 'other' })

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
      const c = await api<EventCostOut[]>(`/events/${id}/costs`)
      setEvent(e)
      setDrinks(d)
      setCosts(c)
      setSettings({
        name: e.name,
        tickets_enabled: e.tickets_enabled ?? e.ticket_mode ?? false,
        entry_enabled: e.entry_enabled ?? false,
        entry_price_cents: e.entry_price_cents ?? 0,
      })
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



  async function addCost(e: React.FormEvent) {
    e.preventDefault()
    try {
      setError(null)
      await api<EventCostOut>(`/events/${id}/costs`, {
        method: 'POST',
        body: JSON.stringify(costInput),
      })
      setCostInput((p) => ({ ...p, label: '', amount_cents: 0 }))
      await load()
    } catch (err: any) {
      setError(err?.message ?? 'Erreur coûts')
    }
  }

  async function deleteCost(costId: number) {
    try {
      setError(null)
      await api(`/events/${id}/costs/${costId}`, { method: 'DELETE' })
      await load()
    } catch (err: any) {
      setError(err?.message ?? 'Erreur suppression coût')
    }
  }

  async function downloadExport(path: string, filename: string) {
    const res = await fetch((import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_BASE ?? 'http://localhost:8000') + path, {
      headers: { Authorization: `Bearer ${localStorage.getItem('tore_partner_token') || ''}` },
    })
    if (!res.ok) throw new Error(`Export HTTP ${res.status}`)
    const blob = await res.blob()
    const a = document.createElement('a')
    const url = URL.createObjectURL(blob)
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  async function patchEvent(body: Partial<{ name: string; tickets_enabled: boolean; entry_enabled: boolean; entry_price_cents: number }>) {
    try {
      setError(null)
      const updated = await api<EventOut>(`/partner/portal/events/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      })
      setEvent(updated)
      setSettings({
        name: updated.name,
        tickets_enabled: updated.tickets_enabled ?? updated.ticket_mode ?? false,
        entry_enabled: updated.entry_enabled ?? false,
        entry_price_cents: updated.entry_price_cents ?? 0,
      })
      setSettingsStatus({ ok: true, message: 'HTTP 200 — Paramètres mis à jour.' })
    } catch (e: any) {
      const status = e?.status ? `HTTP ${e.status}` : 'Erreur'
      const message = e?.message ?? 'Erreur inconnue'
      setSettingsStatus({ ok: false, message: `${status} — ${message}` })
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

  const apiDown = error ? isApiUnavailable(new Error(error)) : false

  if (apiDown) {
    return (
      <Layout title="Event">
        <ApiUnavailable />
      </Layout>
    )
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
          <div style={{ marginTop: 12 }}>
            <Link
              to={`/events/${event.id}/polymarket`}
              style={{
                display: 'inline-block',
                padding: '8px 12px',
                borderRadius: 12,
                border: '1px solid rgba(255,255,255,0.25)',
                color: '#fff',
                textDecoration: 'none',
              }}
            >
              Voir Polymarket Event
            </Link>
          </div>
        </div>
      ) : null}

      <h2 style={{ marginTop: 22 }}>Paramètres event</h2>
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
        <div style={{ display: 'grid', gap: 8 }}>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ opacity: 0.85 }}>Renommer l’event</span>
            <input
              value={settings.name}
              onChange={(e) => setSettings((p) => ({ ...p, name: e.target.value }))}
              style={{ padding: 10, borderRadius: 10, border: '1px solid rgba(255,255,255,0.18)', background: 'transparent', color: '#fff' }}
            />
          </label>
          <button
            type="button"
            onClick={() => patchEvent({ name: settings.name.trim() || event?.name || '' })}
            style={{
              alignSelf: 'flex-start',
              padding: '8px 12px',
              borderRadius: 12,
              border: '1px solid rgba(255,255,255,0.18)',
              background: '#ffffff',
              color: '#000',
              fontWeight: 800,
              cursor: 'pointer',
            }}
          >
            Sauvegarder le nom
          </button>
        </div>

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={settings.tickets_enabled}
              onChange={(e) => setSettings((p) => ({ ...p, tickets_enabled: e.target.checked }))}
            />
            Tickets {settings.tickets_enabled ? 'ON' : 'OFF'}
          </label>
          <button
            type="button"
            onClick={() => patchEvent({ tickets_enabled: settings.tickets_enabled })}
            style={{
              padding: '8px 12px',
              borderRadius: 12,
              border: '1px solid rgba(255,255,255,0.18)',
              background: 'transparent',
              color: '#fff',
              cursor: 'pointer',
            }}
          >
            Mettre à jour tickets
          </button>
        </div>

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={settings.entry_enabled}
              onChange={(e) => setSettings((p) => ({ ...p, entry_enabled: e.target.checked }))}
            />
            Entrée {settings.entry_enabled ? 'ON' : 'OFF'}
          </label>
          <button
            type="button"
            onClick={() => patchEvent({ entry_enabled: settings.entry_enabled })}
            style={{
              padding: '8px 12px',
              borderRadius: 12,
              border: '1px solid rgba(255,255,255,0.18)',
              background: 'transparent',
              color: '#fff',
              cursor: 'pointer',
            }}
          >
            Mettre à jour entrée
          </button>
        </div>

        <div style={{ display: 'grid', gap: 8 }}>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ opacity: 0.85 }}>Prix entrée (€)</span>
            <input
              type="number"
              step="0.01"
              min="0"
              value={(settings.entry_price_cents / 100).toFixed(2)}
              onChange={(e) =>
                setSettings((p) => ({ ...p, entry_price_cents: Math.round(Number(e.target.value || 0) * 100) }))
              }
              style={{ padding: 10, borderRadius: 10, border: '1px solid rgba(255,255,255,0.18)', background: 'transparent', color: '#fff' }}
            />
          </label>
          <button
            type="button"
            onClick={() => patchEvent({ entry_price_cents: settings.entry_price_cents })}
            style={{
              alignSelf: 'flex-start',
              padding: '8px 12px',
              borderRadius: 12,
              border: '1px solid rgba(255,255,255,0.18)',
              background: 'transparent',
              color: '#fff',
              cursor: 'pointer',
            }}
          >
            Mettre à jour le prix
          </button>
        </div>

        {settingsStatus ? (
          <div style={{ color: settingsStatus.ok ? '#c7ffd8' : '#ffb4b4', fontWeight: 700 }}>
            {settingsStatus.message}
          </div>
        ) : null}
      </div>


      <h2 style={{ marginTop: 22 }}>Exports fin de soirée</h2>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 16, padding: 16, background: 'rgba(255,255,255,0.04)' }}>
        <button onClick={() => downloadExport(`/events/${id}/exports/attendance.csv`, `attendance_event_${id}.csv`)}>Attendance CSV</button>
        <button onClick={() => downloadExport(`/events/${id}/exports/report.pdf`, `report_event_${id}.pdf`)}>Report PDF</button>
        <button onClick={() => downloadExport(`/events/${id}/costs/export.csv`, `costs_event_${id}.csv`)}>Costs CSV</button>
      </div>

      <h2 style={{ marginTop: 22 }}>Costs</h2>
      <form onSubmit={addCost} style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr auto', gap: 10, alignItems: 'end', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 16, padding: 16, background: 'rgba(255,255,255,0.04)' }}>
        <label style={{ display: 'grid', gap: 6 }}>
          <span style={{ opacity: 0.85 }}>Label</span>
          <input value={costInput.label} onChange={(e) => setCostInput((p) => ({ ...p, label: e.target.value }))} style={{ padding: 10, borderRadius: 10, border: '1px solid rgba(255,255,255,0.18)', background: 'transparent', color: '#fff' }} />
        </label>
        <label style={{ display: 'grid', gap: 6 }}>
          <span style={{ opacity: 0.85 }}>Amount cents</span>
          <input type="number" min="0" value={costInput.amount_cents} onChange={(e) => setCostInput((p) => ({ ...p, amount_cents: Number(e.target.value || 0) }))} style={{ padding: 10, borderRadius: 10, border: '1px solid rgba(255,255,255,0.18)', background: 'transparent', color: '#fff' }} />
        </label>
        <label style={{ display: 'grid', gap: 6 }}>
          <span style={{ opacity: 0.85 }}>Category</span>
          <select value={costInput.category} onChange={(e) => setCostInput((p) => ({ ...p, category: e.target.value }))} style={{ padding: 10, borderRadius: 10, border: '1px solid rgba(255,255,255,0.18)', background: '#111', color: '#fff' }}>
            <option value="stock">stock</option>
            <option value="location">location</option>
            <option value="staff">staff</option>
            <option value="other">other</option>
          </select>
        </label>
        <button type="submit">Add cost</button>
      </form>

      <div style={{ marginTop: 10, fontWeight: 800 }}>Total costs: {costs.reduce((acc, c) => acc + c.amount_cents, 0)} cents</div>
      <div style={{ marginTop: 8, display: 'grid', gap: 8 }}>
        {costs.map((cost) => (
          <div key={cost.id} style={{ border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, padding: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>{cost.label} — {cost.category} — {cost.amount_cents}c</div>
            <button onClick={() => deleteCost(cost.id)}>Delete</button>
          </div>
        ))}
      </div>

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
