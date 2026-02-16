import './print-share-pack.css'
import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ApiError, api } from '../lib/api'

type LinkValue = { webUrl?: string; deeplink?: string; expiresAt?: string; status?: string; role?: string; code?: string }

type SharePackPayload = {
  event?: {
    id?: number
    name?: string
    startsAt?: string
    venue?: string
    visibility?: string
  }
  metadata?: {
    title?: string
    description?: string
  }
  openUrl?: string
  printPackUrl?: string
  links?: {
    publicShare?: LinkValue
    joinPublic?: LinkValue
    open?: LinkValue
    hunts?: LinkValue
    battles?: LinkValue
    staffInvites?: LinkValue[]
    manageSnapshot?: unknown
    [key: string]: unknown
  }
}

function formatDate(iso?: string) {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('fr-BE')
}

function qrUrl(payload: string) {
  return `https://api.qrserver.com/v1/create-qr-code/?size=220x220&margin=20&data=${encodeURIComponent(payload)}`
}

async function exportNodeToPng(node: HTMLElement, fileName: string) {
  const clone = node.cloneNode(true) as HTMLElement
  clone.style.width = `${node.scrollWidth}px`
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${node.scrollWidth}" height="${node.scrollHeight}">
      <foreignObject width="100%" height="100%">${new XMLSerializer().serializeToString(clone)}</foreignObject>
    </svg>
  `
  const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const img = new Image()
  img.crossOrigin = 'anonymous'
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve()
    img.onerror = reject
    img.src = url
  })
  const canvas = document.createElement('canvas')
  canvas.width = node.scrollWidth * 2
  canvas.height = node.scrollHeight * 2
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas context unavailable')
  ctx.scale(2, 2)
  ctx.drawImage(img, 0, 0)
  URL.revokeObjectURL(url)
  const dataUrl = canvas.toDataURL('image/png')
  const link = document.createElement('a')
  link.href = dataUrl
  link.download = fileName
  link.click()
}

function QrBlock({ label, value }: { label: string; value?: string }) {
  if (!value) return null
  return (
    <div className="print-pack__qr-item">
      <div className="print-pack__qr-meta">
        <strong>{label}</strong>
        <code>{value}</code>
      </div>
      <img src={qrUrl(value)} alt={`QR ${label}`} width={220} height={220} className="print-pack__qr" />
    </div>
  )
}

export default function PrintSharePack({ managed }: { managed: boolean }) {
  const { eventId } = useParams()
  const [pack, setPack] = useState<SharePackPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const contentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let mounted = true
    const path = managed ? `/events/${eventId}/share_pack` : `/share/event/${eventId}`
    api<SharePackPayload>(path)
      .then((data) => {
        if (!mounted) return
        if (managed && !Object.prototype.hasOwnProperty.call(data.links ?? {}, 'staffInvites')) {
          setError('Accès refusé: droits de gestion requis pour le print pack staff.')
          return
        }
        setPack(data)
      })
      .catch((err: unknown) => {
        const apiErr = err as ApiError
        if (mounted) setError(apiErr.message || 'Impossible de charger le print pack')
      })
    return () => {
      mounted = false
    }
  }, [eventId, managed])

  const staffInvites = useMemo(() => {
    const raw = pack?.links?.staffInvites
    return Array.isArray(raw) ? raw : []
  }, [pack])

  const openUrl = pack?.openUrl || pack?.links?.open?.webUrl || pack?.links?.publicShare?.webUrl
  const joinUrl = pack?.links?.joinPublic?.webUrl

  return (
    <div className="print-pack-page">
      <div className="print-pack-toolbar no-print">
        <button className="tore-btn tore-btn--secondary" onClick={() => window.print()}>Imprimer</button>
        <button className="tore-btn tore-btn--secondary" onClick={() => window.alert('Utilise la destination “Save as PDF” dans la boîte de dialogue impression.')}>Télécharger PDF</button>
        <button
          className="tore-btn tore-btn--primary"
          onClick={async () => {
            if (!contentRef.current) return
            await exportNodeToPng(contentRef.current, `tore-share-pack-${eventId}.png`)
          }}
        >
          Télécharger PNG
        </button>
      </div>

      {error ? <div className="tore-alert tore-alert--error">{error}</div> : null}
      {!pack && !error ? <div className="tore-shell">Chargement…</div> : null}

      {pack ? (
        <article className="print-pack" ref={contentRef}>
          <header className="print-pack__header">
            <div>
              <p className="print-pack__brand">TORÈ</p>
              <h1>{pack.event?.name || pack.metadata?.title || 'Event'}</h1>
              <p>{pack.metadata?.description || 'Share pack public imprimable'}</p>
            </div>
            <div className="print-pack__tag">PUBLIC</div>
          </header>

          <section className="print-pack__meta">
            <p><strong>Date/heure:</strong> {formatDate(pack.event?.startsAt)}</p>
            <p><strong>Lieu:</strong> {pack.event?.venue || '—'}</p>
            <p><strong>Open:</strong> {openUrl || '—'}</p>
          </section>

          <section className="print-pack__section">
            <h2>Ouvrir l’event</h2>
            <QrBlock label="Open URL" value={openUrl} />
          </section>

          <section className="print-pack__section">
            <h2>Rejoindre</h2>
            <QrBlock label="Join URL" value={joinUrl} />
          </section>

          {managed ? (
            <section className="print-pack__section">
              <h2>Staff invites</h2>
              {staffInvites.length === 0 ? <p>Aucune invitation staff active.</p> : null}
              {staffInvites.map((invite, idx) => (
                <div className="print-pack__staff" key={`${invite.code || idx}`}>
                  <p><strong>{invite.role || 'STAFF'} · {invite.code || '—'}</strong></p>
                  <p>Expire: {formatDate(invite.expiresAt)} · Statut: {invite.status || '—'}</p>
                  <QrBlock label={`Staff ${invite.role || 'invite'}`} value={invite.webUrl} />
                </div>
              ))}
            </section>
          ) : null}

          {managed ? (
            <section className="print-pack__section">
              <h2>Modules</h2>
              <QrBlock label="Hunt" value={pack.links?.hunts?.webUrl} />
              <QrBlock label="Battles" value={pack.links?.battles?.webUrl} />
              <p className="print-pack__note">WiFi et autres modules: partager uniquement des liens open, jamais les secrets en clair.</p>
            </section>
          ) : null}

          <section className="print-pack__section">
            <h2>Support</h2>
            <p>Si problème: va sur app.tore.be/open</p>
            <p>Fallback HTTPS: https://app.tore.be/open</p>
          </section>
        </article>
      ) : null}
    </div>
  )
}
