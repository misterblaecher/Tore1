import React, { useState } from 'react'
import Layout, { btn, cardStyle, inputStyle } from '../ui/Layout'
import { api } from '../lib/api'

export default function BattlesLive() {
  const [battleId, setBattleId] = useState('')
  const [submitId, setSubmitId] = useState('')
  const [leaderboard, setLeaderboard] = useState<any[]>([])

  const load = async () => {
    if (!battleId) return
    const data = await api<{ rows: any[] }>(`/battles/${battleId}/leaderboard`)
    setLeaderboard(data.rows)
  }

  return <Layout title="Battles Live"><div style={cardStyle()}>
    <input style={inputStyle()} value={battleId} onChange={(e) => setBattleId(e.target.value)} placeholder="battle id" />
    <button style={btn()} onClick={load}>Refresh</button>
    <input style={inputStyle()} value={submitId} onChange={(e) => setSubmitId(e.target.value)} placeholder="submit id" />
    <button style={btn()} onClick={async () => {
      await api(`/battles/${battleId}/validate`, { method: 'POST', body: JSON.stringify({ submit_id: Number(submitId) }) })
      await load()
    }}>Validate submit</button>
    {leaderboard.map((row) => <div key={row.user_id}>{row.user_id}: {row.score}</div>)}
  </div></Layout>
}
