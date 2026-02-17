import './print-share-pack.css'
import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import QrSvg from '../components/QrSvg'
import { ApiError, api } from '../lib/api'

type LinkValue = { webUrl?: string; deeplink?: string; expiresAt?: string; status?: string; role?: string; code?: string }

type SharePackPayload = {
  event?: { id?: number; name?: string; startsAt?: string; venue?: string; visibility?: string }
  metadata?: { title?: string; description?: string }
  openUrl?: string
  printPackUrl?: string
  serverTime?: string
  links?: {
    publicShare?: LinkValue
    joinPublic?: LinkValue
    open?: LinkValue
    hunts?: LinkValue
    battles?: LinkValue
    staffInvites?: LinkValue[]
    [key: string]: unknown
  }
}

type CacheEnvelope = { expiresAt: number; payload: SharePackPayload }

function formatDate(iso?: string) {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('fr-BE')
}

function cacheKey(eventId: string | undefined, managed: boolean) {
  return `${managed ? 'share_manage' : 'share_public'}_${eventId ?? 'unknown'}`
}

function readCache(key: string): SharePackPayload | null {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    const data = JSON.parse(raw) as CacheEnvelope
    if (!data?.expiresAt || Date.now() > data.expiresAt) return null
    return data.payload
  } catch {
    return null
  }
}

function writeCache(key: string, payload: SharePackPayload) {
  const item: CacheEnvelope = { payload, expiresAt: Date.now() + 24 * 60 * 60 * 1000 }
  localStorage.setItem(key, JSON.stringify(item))
}

async function exportNodeToPng(node: HTMLElement, fileName: string) {
  const clone = node.cloneNode(true) as HTMLElement
  clone.style.width = `${node.scrollWidth}px`
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${node.scrollWidth}" height="${node.scrollHeight}"><foreignObject width="100%" height="100%">${new XMLSerializer().serializeToString(clone)}</foreignObject></svg>`
  const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const img = new Image()
  img.crossOrigin = 'anonymous'
  await new Promise<void>((resolve, reject) => { img.onload = () => resolve(); img.onerror = reject; img.src = url })
  const canvas = document.createElement('canvas')
  canvas.width = node.scrollWidth * 2
  canvas.height = node.scrollHeight * 2
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas context unavailable')
  ctx.scale(2, 2)
  ctx.drawImage(img, 0, 0)
  URL.revokeObjectURL(url)
  const link = document.createElement('a')
  link.href = canvas.toDataURL('image/png')
  link.download = fileName
  link.click()
}

function shortCode(code?: string) {
  if (!code) return '—'
  return code.slice(-6)
}

function QrBlock({ label, value, code }: { label: string; value?: string; code?: string }) {
  if (!value) return null
  return (
    <div className="print-pack__qr-item">
      <div className="print-pack__qr-meta">
        <strong>{label}</strong>
        <code>{value}</code>
        <p className="print-pack__short">Code court: {shortCode(code)}</p>
        <button className="tore-btn tore-btn--secondary no-print" onClick={() => navigator.clipboard.writeText(value)}>Copy payload</button>
      </div>
      <QrSvg value={value} className="print-pack__qr" />
    </div>
  )
}

export default function PrintSharePack({ managed }: { managed: boolean }) {
  const { eventId } = useParams()
  const [pack, setPack] = useState<SharePackPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [offlineBanner, setOfflineBanner] = useState(false)
  const [busyRole, setBusyRole] = useState<string | null>(null)
  const contentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let mounted = true
    const path = managed ? `/events/${eventId}/share_pack` : `/share/event/${eventId}`
    const key = cacheKey(eventId, managed)
    api<SharePackPayload>(path)
      .then((data) => {
        if (!mounted) return
        if (managed && !Object.prototype.hasOwnProperty.call(data.links ?? {}, 'staffInvites')) {
          setError('Accès refusé: droits de gestion requis pour le print pack staff.')
          return
        }
        writeCache(key, data)
        setOfflineBanner(false)
        setPack(data)
      })
      .catch((err: unknown) => {
        if (!mounted) return
        const cached = readCache(key)
        if (cached) {
          setPack(cached)
          setOfflineBanner(true)
          return
        }
        const apiErr = err as ApiError
        setError(apiErr.message || 'Impossible de charger le print pack')
      })
    return () => {
      mounted = false
    }
  }, [eventId, managed])

  const staffInvites = useMemo(() => (Array.isArray(pack?.links?.staffInvites) ? pack?.links?.staffInvites ?? [] : []), [pack])
  const openUrl = pack?.openUrl || pack?.links?.open?.webUrl || pack?.links?.publicShare?.webUrl
  const joinUrl = pack?.links?.joinPublic?.webUrl

  async function rotate(role: string) {
    if (!eventId) return
    if (!navigator.onLine) {
      window.alert('Offline: impossible de régénérer maintenant.')
      return
    }
    setBusyRole(role)
    try {
      await api(`/events/${eventId}/staff_invites/rotate`, {
        method: 'POST',
        headers: { 'Idempotency-Key': `rotate-${eventId}-${role}-${Date.now()}` },
        body: JSON.stringify({ role }),
      })
      const refreshed = await api<SharePackPayload>(`/events/${eventId}/share_pack`)
      setPack(refreshed)
      writeCache(cacheKey(eventId, true), refreshed)
      window.alert(`Invite ${role} régénérée`)
    } catch (e) {
      const apiErr = e as ApiError
      window.alert(apiErr.message || 'Échec régénération')
    } finally {
      setBusyRole(null)
    }
  }

  return (
    <div className="print-pack-page">
      <div className="print-pack-toolbar no-print">
        <button className="tore-btn tore-btn--secondary" onClick={() => window.print()}>Imprimer</button>
        <button className="tore-btn tore-btn--secondary" onClick={() => window.alert('Utilise la destination “Save as PDF” dans la boîte de dialogue impression.')}>Télécharger PDF</button>
        <button className="tore-btn tore-btn--primary" onClick={async () => { if (contentRef.current) await exportNodeToPng(contentRef.current, `tore-share-pack-${eventId}.png`) }}>Télécharger PNG</button>
      </div>

      {offlineBanner ? <div className="tore-alert tore-alert--warning">CACHE / OFFLINE — affichage du dernier pack sauvegardé.</div> : null}
      {error ? <div className="tore-alert tore-alert--error">{error}</div> : null}
      {!pack && !error ? <div className="tore-shell">Chargement…</div> : null}

      {pack ? (
        <article className="print-pack" ref={contentRef}>
          <header className="print-pack__header">
            <div><p className="print-pack__brand">TORÈ</p><h1>{pack.event?.name || pack.metadata?.title || 'Event'}</h1><p>{pack.metadata?.description || 'Share pack public imprimable'}</p></div>
            <div className="print-pack__tag">{managed ? 'MANAGED' : 'PUBLIC'}</div>
          </header>
          <section className="print-pack__meta">
            <p><strong>Date/heure:</strong> {formatDate(pack.event?.startsAt)}</p>
            <p><strong>Lieu:</strong> {pack.event?.venue || '—'}</p>
            <p><strong>Open:</strong> {openUrl || '—'}</p>
          </section>
          <section className="print-pack__section"><h2>Ouvrir l’event</h2><QrBlock label="Open URL" value={openUrl} /></section>
          <section className="print-pack__section"><h2>Rejoindre</h2><QrBlock label="Join URL" value={joinUrl} /></section>
          {managed ? (
            <section className="print-pack__section">
              <h2>Staff invites</h2>
              {staffInvites.length === 0 ? <p>Aucune invitation staff active.</p> : null}
              {staffInvites.map((invite, idx) => (
                <div className="print-pack__staff" key={`${invite.code || idx}`}>
                  <p><strong>{invite.role || 'STAFF'} · {invite.code || '—'}</strong></p>
                  <p>Expire: {formatDate(invite.expiresAt)} · Statut: {invite.status || '—'}</p>
                  <div className="no-print">
                    <button className="tore-btn tore-btn--secondary" onClick={() => navigator.clipboard.writeText(invite.webUrl || '')}>Copier lien staff</button>
                    <button className="tore-btn tore-btn--primary" disabled={busyRole === invite.role} onClick={() => rotate((invite.role || '').toUpperCase())}>Regenerate staff QR</button>
                  </div>
                  <QrBlock label={`Staff ${invite.role || 'invite'}`} value={invite.webUrl} code={invite.code} />
                </div>
              ))}
            </section>
          ) : null}
          <section className="print-pack__section"><h2>Support</h2><p>Si problème: va sur app.tore.be/open</p><p>Fallback HTTPS: https://app.tore.be/open</p></section>
          <footer className="print-pack__footer">Generated at {formatDate(pack.serverTime || new Date().toISOString())}</footer>
        </article>
      ) : null}
    </div>
  )
}
