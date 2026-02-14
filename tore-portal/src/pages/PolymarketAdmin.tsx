import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'

export default function PolymarketAdmin() {
  const { eventId } = useParams()
  const [bets, setBets] = useState<any[]>([])

  const load = async () => {
    if (!eventId) return
    const data = await api<any>(`/partner/portal/polymarket/event/${eventId}`)
    setBets(data.bets || [])
  }

  useEffect(() => {
    load()
  }, [eventId])

  const resolveBet = async (betId: number) => {
    await api(`/partner/portal/polymarket/bets/${betId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ outcome: 'YES' }),
    })
    load()
  }

  const finalizeBet = async (betId: number) => {
    await api(`/partner/portal/polymarket/bets/${betId}/finalize`, { method: 'POST' })
    load()
  }

  return (
    <Layout title="Polymarket Event Admin">
      <ul>
        {bets.map((bet) => {
          const disputed = bet.disputes_count && bet.disputes_count > 0
          return (
            <li key={bet.id}>
              #{bet.id} {bet.question} [{bet.status}]
              <button onClick={() => resolveBet(bet.id)}>Resolve</button>
              <button disabled={disputed} onClick={() => finalizeBet(bet.id)}>
                Finalize
              </button>
            </li>
          )
        })}
      </ul>
    </Layout>
  )
}
