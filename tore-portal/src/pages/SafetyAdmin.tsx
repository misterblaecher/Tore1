import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout, { btn, cardStyle } from '../ui/Layout'
import { api } from '../lib/api'

export default function SafetyAdmin() {
  const { eventId } = useParams()
  const [stats, setStats] = useState<any>(null)

  const load = async () => {
    if (!eventId) return
    setStats(await api<any>(`/partner/portal/safety/event/${eventId}/stats`))
  }

  useEffect(() => { load() }, [eventId])

  return <Layout title="Safety Admin"><div style={cardStyle()}>
    <button style={btn()} onClick={load}>Refresh stats</button>
    <pre>{JSON.stringify(stats, null, 2)}</pre>
  </div></Layout>
}