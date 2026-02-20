import { useEffect, useMemo, useState } from 'react'
import { API_BASE, createShortlink } from '../lib/api'

type OpenPayload = {
  ok: boolean
  type: string
  target: Record<string, unknown>
  deeplink: string
  webFallback: string
  expiresAt?: string | null
  title?: string
  description?: string
}

type JoinPreviewPayload = {
  kind: string
  actionHint?: string
  normalizedCode?: string
}

const PLAY_STORE_URL = 'https://play.google.com/store/apps/details?id=be.tore.app'
const APP_STORE_URL = 'https://apps.apple.com/app/id0000000000'

export default function OpenInApp() {
  const params = new URLSearchParams(window.location.search)
  const passthrough = useMemo(() => params.toString(), [params])
  const type = (params.get('type') || '').trim().toLowerCase()
  const joinCode = (params.get('code') || '').trim().toUpperCase()

  const [payload, setPayload] = useState<OpenPayload | null>(null)
  const [joinPreview, setJoinPreview] = useState<JoinPreviewPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showInstall, setShowInstall] = useState(false)
  const [shortUrl, setShortUrl] = useState<string>('')
  const manualCode = String((payload?.target?.code as string | undefined) || joinCode || '').trim()

  useEffect(() => {
    document.title = 'Ouvrir dans TORÈ'
    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/open?${passthrough}`)
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const data = (await response.json()) as OpenPayload
        setPayload(data)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Impossible de résoudre le lien')
      }
    })()
  }, [passthrough])

  useEffect(() => {
    if (!joinCode) return
    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/codes/preview?code=${encodeURIComponent(joinCode)}`)
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const data = (await response.json()) as JoinPreviewPayload
        setJoinPreview(data)
      } catch {
        setJoinPreview(null)
      }
    })()
  }, [type, joinCode])


  useEffect(() => {
    const id = Number(params.get('id') || '0')
    if (!id || !['event', 'orga'].includes(type)) return
    void (async () => {
      const short = await createShortlink(type === 'event' ? { kind: 'event_share', event_id: id } : { kind: 'orga_share', orga_id: id })
      if (short?.shortUrl) setShortUrl(short.shortUrl)
    })()
  }, [params, type])

  useEffect(() => {
    if (!payload?.deeplink) return
    const openTimer = window.setTimeout(() => {
      window.location.href = payload.deeplink
    }, 300)
    const fallbackTimer = window.setTimeout(() => {
      setShowInstall(true)
    }, 1500)
    return () => {
      window.clearTimeout(openTimer)
      window.clearTimeout(fallbackTimer)
    }
  }, [payload])

  const shareUrl = shortUrl || `${window.location.origin}/open?${passthrough}`
  const shareText = encodeURIComponent(`Ouvre TORÈ : ${shareUrl}`)
  const visibleCode = (joinPreview?.normalizedCode || manualCode || '').slice(-4)

  return (
    <main style={{ maxWidth: 480, margin: '48px auto', padding: 16, fontFamily: 'Inter, sans-serif' }}>
      <h1 style={{ marginBottom: 8 }}>Ouvrir dans TORÈ</h1>
      <p style={{ marginTop: 0, opacity: 0.8 }}>Si l’app n’est pas installée, utilise les liens ci-dessous.</p>

      {error && <p style={{ color: '#e25959' }}>{error}</p>}


      {shortUrl && (
        <button
          type="button"
          onClick={() => void navigator.clipboard?.writeText(shortUrl)}
          style={{ marginTop: 8, width: '100%', padding: '10px 16px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.2)', background: 'transparent', color: '#fff' }}
        >
          Copier lien court
        </button>
      )}

      {payload?.type === 'join' && (
        <section style={{ marginBottom: 12, padding: 12, borderRadius: 8, border: '1px solid rgba(255,255,255,0.15)' }}>
          {joinPreview?.actionHint === 'LOGIN_REQUIRED' ? (
            <>
              <h2 style={{ margin: '0 0 6px 0', fontSize: 18 }}>Connexion requise</h2>
              <p style={{ margin: 0, opacity: 0.85 }}>Connecte-toi dans TORÈ puis entre le code manuellement.</p>
            </>
          ) : (
            <>
              <h2 style={{ margin: '0 0 6px 0', fontSize: 18 }}>Code prêt</h2>
              <p style={{ margin: 0, opacity: 0.85 }}>Ouvre TORÈ puis utilise “Entrer un code”.</p>
            </>
          )}
          <p style={{ margin: '8px 0 0', opacity: 0.7 }}>Code: <strong>••••{visibleCode}</strong></p>
        </section>
      )}


      {manualCode && (
        <section style={{ marginBottom: 12, padding: 12, borderRadius: 8, border: '1px dashed rgba(255,255,255,0.25)' }}>
          <h2 style={{ margin: '0 0 6px 0', fontSize: 16 }}>Code manuel</h2>
          <p style={{ margin: 0, opacity: 0.85 }}>Copie ce code puis entre ce code dans l’app TORÈ.</p>
          <button
            type="button"
            onClick={() => void navigator.clipboard?.writeText(manualCode)}
            style={{ marginTop: 8, width: '100%', textAlign: 'left', padding: 8, borderRadius: 6, border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.06)', color: '#fff' }}
          >
            <code>••••{visibleCode}</code>
          </button>
        </section>
      )}

      <section style={{ marginTop: 12, padding: 12, borderRadius: 8, border: '1px dashed rgba(255,255,255,0.2)' }}>
        <p style={{ margin: 0, opacity: 0.8 }}>Si ça ne s’ouvre pas : ouvre TORÈ → Entrer un code.</p>
      </section>

      <button
        type="button"
        onClick={() => payload?.deeplink && (window.location.href = payload.deeplink)}
        disabled={!payload?.deeplink}
        style={{ width: '100%', padding: '12px 16px', borderRadius: 8, border: 0, background: '#5f5cff', color: '#fff', fontWeight: 700 }}
      >
        Ouvrir dans TORÈ
      </button>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <a href={`https://wa.me/?text=${shareText}`} style={{ flex: 1, textAlign: 'center', padding: '10px 12px', borderRadius: 8, background: 'rgba(255,255,255,0.08)', color: '#fff', textDecoration: 'none' }}>WhatsApp</a>
        <a href={`sms:?body=${shareText}`} style={{ flex: 1, textAlign: 'center', padding: '10px 12px', borderRadius: 8, background: 'rgba(255,255,255,0.08)', color: '#fff', textDecoration: 'none' }}>SMS</a>
      </div>


      {shortUrl && (
        <button
          type="button"
          onClick={() => void navigator.clipboard?.writeText(shortUrl)}
          style={{ marginTop: 8, width: '100%', padding: '10px 16px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.2)', background: 'transparent', color: '#fff' }}
        >
          Copier lien court
        </button>
      )}

      {payload?.type === 'join' && (
        <button
          type="button"
          onClick={() => payload?.deeplink && (window.location.href = payload.deeplink)}
          disabled={!payload?.deeplink}
          style={{ marginTop: 8, width: '100%', padding: '10px 16px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.2)', background: 'transparent', color: '#fff' }}
        >
          Entrer le code dans l’app
        </button>
      )}

      {payload?.type === 'staff_invite' && (
        <section style={{ marginTop: 16, padding: 12, borderRadius: 8, border: '1px solid rgba(255,255,255,0.15)' }}>
          <h2 style={{ margin: '0 0 6px 0', fontSize: 18 }}>Invitation staff</h2>
          <p style={{ margin: 0, opacity: 0.8 }}>
            Role: <strong>{String(payload.target?.role ?? 'STAFF')}</strong>
          </p>
          <p style={{ marginTop: 6, opacity: 0.7 }}>Tu devras être connecté dans l’app.</p>
        </section>
      )}

      {payload?.type === 'staff_backup' && (
        <section style={{ marginTop: 16, padding: 12, borderRadius: 8, border: '1px solid rgba(255,255,255,0.15)' }}>
          <h2 style={{ margin: '0 0 6px 0', fontSize: 18 }}>Backup code staff</h2>
          <p style={{ margin: 0, opacity: 0.8 }}>Connecte-toi dans TORÈ puis entre le code backup manuellement.</p>
        </section>
      )}

      {showInstall && (
        <div style={{ marginTop: 12, display: 'grid', gap: 8 }}>
          <a href={PLAY_STORE_URL} target="_blank" rel="noreferrer" style={{ color: '#5f5cff' }}>
            Android · Google Play
          </a>
          <a href={APP_STORE_URL} target="_blank" rel="noreferrer" style={{ color: '#5f5cff' }}>
            iOS · App Store
          </a>
        </div>
      )}

      {import.meta.env.DEV && (
        <pre style={{ marginTop: 20, padding: 12, borderRadius: 8, background: '#161622', overflowX: 'auto' }}>
          {JSON.stringify(payload, null, 2)}
        </pre>
      )}
    </main>
  )
}
