import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout, { btn, cardStyle } from '../ui/Layout'
import { api } from '../lib/api'

type Team = { id: number; name: string; score: number }
type BattleStats = { id: number; title: string; teams: Team[] }

export default function BattlePublic() {
  const { id } = useParams()
  const battleId = Number(id)
  const [battle, setBattle] = useState<BattleStats | null>(null)

  const load = async () => {
    if (!battleId) return
    const data = await api<BattleStats>(`/battles/${battleId}`)
    setBattle(data)
  }

  useEffect(() => {
    load()
  }, [battleId])

  return (
    <Layout title={battle ? battle.title : 'Battle'}>
      <div style={cardStyle()}>
        {battle?.teams.map((team) => (
          <div key={team.id} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <strong>{team.name}</strong>
            <span>{team.score}</span>
            <button style={btn('ghost')} onClick={async () => {
              await api(`/battles/${battleId}/join`, { method: 'POST', body: JSON.stringify({ team_id: team.id }) })
              await load()
            }}>Rejoindre</button>
          </div>
        ))}
      </div>
    </Layout>
  )
}
