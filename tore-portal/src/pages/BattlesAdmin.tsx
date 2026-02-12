import React, { useEffect, useState } from 'react'
import Layout, { btn, cardStyle, inputStyle } from '../ui/Layout'
import { api } from '../lib/api'

type EventOut = { id: number; name: string }
type TeamOut = { id: number; name: string; color?: string | null; score: number }
type BattleOut = {
  id: number
  title: string
  mode: 'teams' | 'solo'
  is_active: boolean
  teams: TeamOut[]
  recent_actions?: Array<{ id: number; team_id?: number | null; kind: string; delta: number }>
}

export default function BattlesAdmin() {
  const [events, setEvents] = useState<EventOut[]>([])
  const [eventId, setEventId] = useState<number | null>(null)
  const [title, setTitle] = useState('Battle')
  const [battles, setBattles] = useState<BattleOut[]>([])

  const load = async (eid?: number | null) => {
    const id = eid ?? eventId
    if (!id) return
    const rows = await api<BattleOut[]>(`/partner/portal/battles?event_id=${id}`)
    setBattles(rows)
  }

  useEffect(() => {
    ;(async () => {
      const rows = await api<EventOut[]>('/partner/portal/events')
      setEvents(rows)
      if (rows[0]) {
        setEventId(rows[0].id)
        await load(rows[0].id)
      }
    })()
  }, [])

  return (
    <Layout title="Battles admin">
      <div style={cardStyle()}>
        <div style={{ display: 'grid', gap: 8 }}>
          <select value={eventId ?? ''} onChange={async (e) => {
            const id = Number(e.target.value)
            setEventId(id)
            await load(id)
          }} style={inputStyle()}>
            {events.map((ev) => <option key={ev.id} value={ev.id}>{ev.name}</option>)}
          </select>
          <input value={title} onChange={(e) => setTitle(e.target.value)} style={inputStyle()} placeholder="Titre battle" />
          <button style={btn()} onClick={async () => {
            if (!eventId) return
            await api('/partner/portal/battles', {
              method: 'POST',
              body: JSON.stringify({
                event_id: eventId,
                title,
                mode: 'teams',
                teams: [{ name: 'Team A' }, { name: 'Team B' }],
              }),
            })
            await load(eventId)
          }}>Créer battle</button>
        </div>
      </div>

      <div style={{ marginTop: 16, display: 'grid', gap: 12 }}>
        {battles.map((battle) => (
          <div key={battle.id} style={cardStyle()}>
            <div style={{ fontWeight: 800 }}>{battle.title} #{battle.id}</div>
            <div style={{ marginTop: 8, display: 'grid', gap: 8 }}>
              {battle.teams.map((team) => (
                <div key={team.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <strong>{team.name}</strong>
                  <span>{team.score}</span>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button style={btn('ghost')} onClick={async () => {
                      await api(`/partner/portal/battles/${battle.id}/action`, {
                        method: 'POST',
                        body: JSON.stringify({ team_id: team.id, kind: 'AFFOND', delta: 1, idempotency_key: `${battle.id}-${team.id}-${Date.now()}-p` }),
                      })
                      await load(eventId)
                    }}>+1</button>
                    <button style={btn('ghost')} onClick={async () => {
                      await api(`/partner/portal/battles/${battle.id}/action`, {
                        method: 'POST',
                        body: JSON.stringify({ team_id: team.id, kind: 'PENALTY', delta: -1, idempotency_key: `${battle.id}-${team.id}-${Date.now()}-m` }),
                      })
                      await load(eventId)
                    }}>-1</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Layout>
  )
}
