import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'
import { Button, Card, InlineAlert } from '../lib/ui'

type QrItem = {
  type: string
  payload: string
  expiresAt: string
  tokenId: string
}

export default function EventQrPack() {
  const { eventId } = useParams()
  const [items, setItems] = useState<QrItem[]>([])
  const [eventName, setEventName] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!eventId) return
    Promise.all([
      api<any>(`/partner/portal/events/${eventId}`),
      api<any>(`/partner/portal/orga/events/${eventId}/qr_pack`, {
        method: 'POST',
        headers: { 'Idempotency-Key': `qr-pack-view-${eventId}` },
      }),
    ])
      .then(([event, pack]) => {
        setEventName(event?.name || `Event #${eventId}`)
        setItems(pack?.items || [])
      })
      .catch((e: any) => setError(e?.message ?? 'Erreur chargement QR pack'))
  }, [eventId])

  const copy = async (raw: string) => {
    try {
      await navigator.clipboard.writeText(raw)
    } catch {
      setError('Copie impossible sur ce navigateur.')
    }
  }

  return (
    <Layout title="Pack QR Event">
      <Card>
        <strong>{eventName}</strong>
        <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
          <Button onClick={() => window.print()}>Print</Button>
          <Link to="/" className="btn">Dashboard</Link>
        </div>
      </Card>
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      <div style={{ display: 'grid', gap: 12, marginTop: 12 }}>
        {items.map((item) => (
          <Card key={item.tokenId}>
            <div style={{ fontSize: 24, fontWeight: 800 }}>{item.type}</div>
            <div style={{ marginTop: 8, fontSize: 12, opacity: 0.75 }}>Expire: {new Date(item.expiresAt).toLocaleString()}</div>
            <textarea readOnly value={item.payload} style={{ width: '100%', minHeight: 90, marginTop: 8 }} />
            <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
              <Button variant="secondary" onClick={() => copy(item.payload)}>Copy deep link</Button>
            </div>
          </Card>
        ))}
      </div>
    </Layout>
  )
}
