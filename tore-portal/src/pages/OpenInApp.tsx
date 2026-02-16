import { useEffect, useMemo, useState } from 'react'
import { API_BASE } from '../lib/api'

type OpenPayload = {
  ok: boolean
  type: string
  target: Record<string, unknown>
  deeplink: string
  webFallback: string
  expiresAt?: string | null
}

const PLAY_STORE_URL = 'https://play.google.com/store/apps/details?id=be.tore.app'
const APP_STORE_URL = 'https://apps.apple.com/app/id0000000000'

export default function OpenInApp() {
  const params = new URLSearchParams(window.location.search)
  const passthrough = useMemo(() => params.toString(), [params])
  const [payload, setPayload] = useState<OpenPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showInstall, setShowInstall] = useState(false)

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

  return (
    <main style={{ maxWidth: 480, margin: '48px auto', padding: 16, fontFamily: 'Inter, sans-serif' }}>
      <h1 style={{ marginBottom: 8 }}>Ouvrir dans TORÈ</h1>
      <p style={{ marginTop: 0, opacity: 0.8 }}>Si l’app n’est pas installée, utilise les liens ci-dessous.</p>

      {error && <p style={{ color: '#e25959' }}>{error}</p>}

      <button
        type="button"
        onClick={() => payload?.deeplink && (window.location.href = payload.deeplink)}
        disabled={!payload?.deeplink}
        style={{ width: '100%', padding: '12px 16px', borderRadius: 8, border: 0, background: '#5f5cff', color: '#fff', fontWeight: 700 }}
      >
        Ouvrir dans TORÈ
      </button>

      {payload?.type === 'staff_invite' && (
        <section style={{ marginTop: 16, padding: 12, borderRadius: 8, border: '1px solid rgba(255,255,255,0.15)' }}>
          <h2 style={{ margin: '0 0 6px 0', fontSize: 18 }}>Invitation staff</h2>
          <p style={{ margin: 0, opacity: 0.8 }}>
            Role: <strong>{String(payload.target?.role ?? 'STAFF')}</strong>
          </p>
          <p style={{ marginTop: 6, opacity: 0.7 }}>Tu devras être connecté dans l’app.</p>
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
