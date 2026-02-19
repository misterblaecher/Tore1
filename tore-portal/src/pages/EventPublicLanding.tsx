import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { API_BASE } from '../lib/api'

const PLAY_STORE_URL = 'https://play.google.com/store/apps/details?id=be.tore.app'
const APP_STORE_URL = 'https://apps.apple.com/app/id0000000000'

type EventPublicPayload = {
  id: number
  name: string
  startAt?: string | null
  endAt?: string | null
  host?: { name?: string | null }
  venue?: { name?: string | null; barName?: string | null }
  links?: { webUrl?: string; openUrl?: string; deeplink?: string }
}

export default function EventPublicLanding() {
  const { eventId } = useParams()
  const [payload, setPayload] = useState<EventPublicPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showInstall, setShowInstall] = useState(false)
  const openLink = useMemo(() => `${window.location.origin}/open?type=event&id=${eventId}`, [eventId])

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch(`${API_BASE}/events/${eventId}/public`)
        if (!res.ok) throw new Error('not_public')
        setPayload((await res.json()) as EventPublicPayload)
      } catch {
        setError('Event privé / lien invalide')
      }
    })()
  }, [eventId])

  useEffect(() => {
    if (!payload?.links?.deeplink) return
    const t1 = window.setTimeout(() => {
      window.location.href = payload.links?.deeplink || ''
    }, 300)
    const t2 = window.setTimeout(() => setShowInstall(true), 1500)
    return () => {
      window.clearTimeout(t1)
      window.clearTimeout(t2)
    }
  }, [payload])

  return (
    <main style={{ maxWidth: 520, margin: '48px auto', padding: 16 }}>
      <h1>Ouvrir dans TORÈ</h1>
      {error && <p>{error}</p>}
      {payload && (
        <>
          <h2>{payload.name}</h2>
          <p>{payload.host?.name ?? 'Host'} · {payload.venue?.name ?? payload.venue?.barName ?? 'Lieu à venir'}</p>
          <button type="button" onClick={() => payload.links?.deeplink && (window.location.href = payload.links.deeplink)}>Ouvrir dans TORÈ</button>
          <button type="button" onClick={() => navigator.clipboard.writeText(openLink)} style={{ marginLeft: 8 }}>Copier lien</button>
        </>
      )}
      {showInstall && (
        <p>
          <a href={PLAY_STORE_URL}>Installer Android</a> · <a href={APP_STORE_URL}>Installer iOS</a>
        </p>
      )}
    </main>
  )
}
