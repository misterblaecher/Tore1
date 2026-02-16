import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'

type Hunt = {
  id: number
  title: string
  description?: string | null
  startsAt: string
  endsAt: string
  isActive: boolean
}

export default function OrgaEventHunts() {
  const { eventId } = useParams()
  const [hunts, setHunts] = useState<Hunt[]>([])
  const [title, setTitle] = useState('Campus Hunt')
  const [description, setDescription] = useState('Chasse QR')
  const [rulesText, setRulesText] = useState('Respect des règles')
  const [checkpointsText, setCheckpointsText] = useState('Checkpoint A|10\nCheckpoint B|20')
  const [message, setMessage] = useState<string | null>(null)
  const [qrPack, setQrPack] = useState<any[] | null>(null)
  const [isOnline, setIsOnline] = useState<boolean>(typeof navigator === 'undefined' ? true : navigator.onLine)

  useEffect(() => {
    const onOnline = () => setIsOnline(true)
    const onOffline = () => setIsOnline(false)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [])

  const refresh = async () => {
    if (!eventId) return
    const data = await api<Hunt[]>(`/partner/portal/orga/events/${eventId}/hunts`)
    setHunts(data)
  }

  useEffect(() => {
    refresh().catch((e: any) => setMessage(e?.message ?? 'Erreur chargement hunts'))
  }, [eventId])

  async function createHunt() {
    if (!eventId || !isOnline) return
    const checkpoints = checkpointsText
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line, idx) => {
        const [label, pointsRaw] = line.split('|')
        return { label: label?.trim() || `Checkpoint ${idx + 1}`, points: Math.max(1, Number(pointsRaw || '10')), orderIndex: idx + 1 }
      })
    const startsAt = new Date().toISOString()
    const endsAt = new Date(Date.now() + 2 * 3600 * 1000).toISOString()
    const payload = await api<any>(`/partner/portal/orga/events/${eventId}/hunts`, {
      method: 'POST',
      headers: { 'Idempotency-Key': `hunt-create-${eventId}-${Date.now()}` },
      body: JSON.stringify({ title, description, startsAt, endsAt, rulesText, checkpoints }),
    })
    setMessage('Hunt créée')
    const pack = await api<any>(`/partner/portal/orga/hunts/${payload.id}/qr_pack`)
    setQrPack(pack.items || [])
    await refresh()
  }

  async function closeHunt(huntId: number) {
    if (!isOnline) return
    await api(`/partner/portal/orga/hunts/${huntId}/close`, {
      method: 'POST',
      headers: { 'Idempotency-Key': `hunt-close-${huntId}-${Date.now()}` },
    })
    setMessage('Hunt clôturée')
    await refresh()
  }

  return (
    <Layout title="Hunts ORGA">
      {!isOnline ? <p style={{ color: '#ffca7a' }}>Offline: writes bloqués.</p> : null}
      {message ? <p>{message}</p> : null}
      <div style={{ display: 'grid', gap: 8, maxWidth: 680 }}>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Titre" />
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description" />
        <textarea value={rulesText} onChange={(e) => setRulesText(e.target.value)} placeholder="Règles" />
        <textarea value={checkpointsText} onChange={(e) => setCheckpointsText(e.target.value)} rows={4} placeholder="Label|Points" />
        <button onClick={createHunt} disabled={!isOnline}>Créer Hunt + pack QR</button>
      </div>

      <h3>Hunts</h3>
      <ul>
        {hunts.map((hunt) => (
          <li key={hunt.id} style={{ marginBottom: 8 }}>
            #{hunt.id} {hunt.title} — {hunt.isActive ? 'ACTIVE' : 'CLOSED'}
            {hunt.isActive ? <button style={{ marginLeft: 8 }} onClick={() => closeHunt(hunt.id)} disabled={!isOnline}>Close</button> : null}
          </li>
        ))}
      </ul>

      {qrPack ? (
        <div>
          <h3>QR Pack</h3>
          <ul>
            {qrPack.map((item) => (
              <li key={item.checkpointId}>
                {item.label} (+{item.points})
                <pre style={{ whiteSpace: 'pre-wrap' }}>{item.deeplink}</pre>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Layout>
  )
}
