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
  displaySuffix?: string
  copyValue?: string | null
  copyHint?: string | null
  requiresAuth?: boolean
  openUrl?: string
}

const PLAY_STORE_URL = 'https://play.google.com/store/apps/details?id=be.tore.app'
const APP_STORE_URL = 'https://apps.apple.com/app/id0000000000'
const PRIVATE_HINT = 'Connexion requise. Ouvre TORÈ → Entrer un code.'

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
  const [copiedTrace, setCopiedTrace] = useState<string>('')
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
  }, [joinCode])

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

  const openUrl = joinPreview?.openUrl || payload?.webFallback || `${window.location.origin}/open?${passthrough}`
  const primaryUrl = shortUrl || openUrl
  const shareText = encodeURIComponent(`Ouvre TORÈ : ${primaryUrl}`)
  const visibleCode = joinPreview?.displaySuffix || `…${(joinPreview?.normalizedCode || manualCode || '').slice(-6)}`

  const copyLink = async () => {
    await navigator.clipboard?.writeText(primaryUrl)
    if (import.meta.env.DEV) setCopiedTrace(`copied: ${shortUrl ? 'short' : 'open'} @ ${new Date().toISOString()}`)
    window.alert('Lien copié')
  }

  const copyManualCode = async () => {
    const value = joinPreview?.copyValue || manualCode
    if (!value) {
      window.alert(joinPreview?.copyHint || PRIVATE_HINT)
      return
    }
    await navigator.clipboard?.writeText(value)
    window.alert(joinPreview?.copyHint || 'Code copié')
  }

  return (
    <main style={{ maxWidth: 480, margin: '48px auto', padding: 16, fontFamily: 'Inter, sans-serif' }}>
      <h1 style={{ marginBottom: 8 }}>Ouvrir dans TORÈ</h1>
      <p style={{ marginTop: 0, opacity: 0.8 }}>Si l’app n’est pas installée, utilise les liens ci-dessous.</p>

      {error && <p style={{ color: '#e25959' }}>{error}</p>}

      <section style={{ marginBottom: 12, padding: 12, borderRadius: 8, border: '1px dashed rgba(255,255,255,0.25)' }}>
        <h2 style={{ margin: '0 0 6px 0', fontSize: 16 }}>Partager</h2>
        <button type="button" onClick={() => void copyLink()} style={{ marginTop: 8, width: '100%', padding: '10px 16px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.2)', background: 'transparent', color: '#fff' }}>
          Copier lien
        </button>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <a href={`https://wa.me/?text=${shareText}`} style={{ flex: 1, textAlign: 'center', padding: '10px 12px', borderRadius: 8, background: 'rgba(255,255,255,0.08)', color: '#fff', textDecoration: 'none' }}>WhatsApp</a>
          <a href={`sms:?body=${shareText}`} style={{ flex: 1, textAlign: 'center', padding: '10px 12px', borderRadius: 8, background: 'rgba(255,255,255,0.08)', color: '#fff', textDecoration: 'none' }}>SMS</a>
        </div>
      </section>

      {(joinPreview?.requiresAuth || payload?.type === 'staff_backup' || payload?.type === 'staff_invite') && (
        <section style={{ marginTop: 12, padding: 12, borderRadius: 8, border: '1px dashed rgba(255,255,255,0.2)' }}>
          <p style={{ margin: 0, opacity: 0.8 }}>{PRIVATE_HINT}</p>
        </section>
      )}

      {manualCode && (
        <section style={{ marginBottom: 12, marginTop: 12, padding: 12, borderRadius: 8, border: '1px dashed rgba(255,255,255,0.25)' }}>
          <h2 style={{ margin: '0 0 6px 0', fontSize: 16 }}>Code manuel</h2>
          <p style={{ margin: 0, opacity: 0.85 }}>Suffixe: <strong>{visibleCode}</strong></p>
          <button type="button" onClick={() => void copyManualCode()} style={{ marginTop: 8, width: '100%', textAlign: 'left', padding: 8, borderRadius: 6, border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.06)', color: '#fff' }}>
            <code>Copier code</code>
          </button>
        </section>
      )}

      <button
        type="button"
        onClick={() => payload?.deeplink && (window.location.href = payload.deeplink)}
        disabled={!payload?.deeplink}
        style={{ width: '100%', padding: '12px 16px', borderRadius: 8, border: 0, background: '#5f5cff', color: '#fff', fontWeight: 700 }}
      >
        Ouvrir dans TORÈ
      </button>

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
          {copiedTrace || 'copied: n/a'}
        </pre>
      )}
    </main>
  )
}
