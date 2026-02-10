import React from 'react'
import { useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import PolymarketList from './PolymarketList'

export default function PolymarketEvent() {
  const { eventId } = useParams()
  const id = Number(eventId)
  if (!Number.isFinite(id)) {
    return (
      <Layout title="Polymarket — Event">
        <div style={{ color: '#ffb4b4', fontWeight: 700 }}>Event invalide.</div>
      </Layout>
    )
  }
  return <PolymarketList scope="EVENT" title={`Polymarket — Event ${id}`} eventId={id} />
}
