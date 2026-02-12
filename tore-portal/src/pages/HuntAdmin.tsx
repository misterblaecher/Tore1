import React, { useState } from 'react'
import Layout from '../ui/Layout'
import { api } from '../lib/api'

type HuntOut = {
  id: number
  event_id: number
  name: string
  reward_tickets: number
}

type HuntPointOut = {
  id: number
  name: string
  hint?: string | null
  sort_order: number
  secret_code: string
  qr_payload: string
  route_front: string
}

type HuntStatsOut = {
  participants: number
  scans_total: number
  completion_count: number
}

export default function HuntAdmin() {
  const [eventId, setEventId] = useState('')
  const [name, setName] = useState('QR Hunt')
  const [rewardTickets, setRewardTickets] = useState(0)
  const [hunt, setHunt] = useState<HuntOut | null>(null)
  const [points, setPoints] = useState<HuntPointOut[]>([])
  const [stats, setStats] = useState<HuntStatsOut | null>(null)
  const [pointName, setPointName] = useState('')
  const [pointHint, setPointHint] = useState('')
  const [pointOrder, setPointOrder] = useState(0)
  const [message, setMessage] = useState('')

  async function createHunt() {
    setMessage('')
    const payload = await api<HuntOut>('/partner/portal/hunt', {
      method: 'POST',
      body: JSON.stringify({
        event_id: Number(eventId),
        name,
        reward_tickets: rewardTickets,
      }),
    })
    setHunt(payload)
    await reload(payload.id)
    setMessage('Hunt créée')
  }

  async function reload(huntId: number) {
    const [pointRows, statRows] = await Promise.all([
      api<HuntPointOut[]>(`/partner/portal/hunt/${huntId}/points`),
      api<HuntStatsOut>(`/partner/portal/hunt/${huntId}/stats`),
    ])
    setPoints(pointRows)
    setStats(statRows)
  }

  async function addPoint() {
    if (!hunt) return
    await api(`/partner/portal/hunt/${hunt.id}/points`, {
      method: 'POST',
      body: JSON.stringify({
        name: pointName,
        hint: pointHint || null,
        sort_order: pointOrder,
      }),
    })
    setPointName('')
    setPointHint('')
    setPointOrder(pointOrder + 1)
    await reload(hunt.id)
  }

  return (
    <Layout title="Hunt Admin">
      <div style={{ display: 'grid', gap: 10, maxWidth: 620 }}>
        <input placeholder="event_id" value={eventId} onChange={(e) => setEventId(e.target.value)} />
        <input placeholder="Nom hunt" value={name} onChange={(e) => setName(e.target.value)} />
        <input
          placeholder="Récompense tickets"
          type="number"
          value={rewardTickets}
          onChange={(e) => setRewardTickets(Number(e.target.value))}
        />
        <button onClick={createHunt}>Créer Hunt</button>
      </div>

      {message ? <p>{message}</p> : null}

      {hunt ? (
        <div style={{ marginTop: 16, display: 'grid', gap: 12 }}>
          <h3>
            Hunt #{hunt.id} — {hunt.name}
          </h3>
          <div style={{ display: 'grid', gap: 8, maxWidth: 620 }}>
            <input placeholder="Nom point" value={pointName} onChange={(e) => setPointName(e.target.value)} />
            <input placeholder="Hint" value={pointHint} onChange={(e) => setPointHint(e.target.value)} />
            <input
              type="number"
              placeholder="Ordre"
              value={pointOrder}
              onChange={(e) => setPointOrder(Number(e.target.value))}
            />
            <button onClick={addPoint}>Ajouter point</button>
          </div>

          <h4>Points</h4>
          <div style={{ display: 'grid', gap: 10 }}>
            {points.map((p) => (
              <div key={p.id} style={{ border: '1px solid rgba(255,255,255,.2)', borderRadius: 8, padding: 10 }}>
                <div>
                  <strong>{p.name}</strong> (order {p.sort_order})
                </div>
                <div style={{ fontFamily: 'monospace', fontSize: 12 }}>{p.qr_payload}</div>
                <button onClick={() => navigator.clipboard.writeText(p.qr_payload)}>Copier payload</button>
              </div>
            ))}
          </div>

          {stats ? (
            <div>
              <h4>Stats</h4>
              <div>Participants: {stats.participants}</div>
              <div>Scans total: {stats.scans_total}</div>
              <div>Completions: {stats.completion_count}</div>
            </div>
          ) : null}
        </div>
      ) : null}
    </Layout>
  )
}
