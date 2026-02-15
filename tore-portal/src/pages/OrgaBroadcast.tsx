import React, { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { ApiError, api } from '../lib/api'
import { Button, Card, InlineAlert } from '../lib/ui'

const DRAFT_KEY = 'orga_broadcast_draft'

type BroadcastItem = {
  id: number
  message: string
  level: 'info' | 'warn' | 'urgent'
  created_at: string
}

export default function OrgaBroadcast() {
  const { eventId } = useParams()
  const [message, setMessage] = useState('')
  const [level, setLevel] = useState<'info' | 'warn' | 'urgent'>('info')
  const [items, setItems] = useState<BroadcastItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [pendingRetry, setPendingRetry] = useState(false)
  const [cooldownUntil, setCooldownUntil] = useState<number | null>(null)
  const [isOnline, setIsOnline] = useState<boolean>(typeof navigator === 'undefined' ? true : navigator.onLine)

  useEffect(() => {
    const draft = localStorage.getItem(`${DRAFT_KEY}_${eventId}`)
    if (draft) setMessage(draft)
  }, [eventId])

  useEffect(() => {
    localStorage.setItem(`${DRAFT_KEY}_${eventId}`, message)
  }, [eventId, message])

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

  const networkMode = useMemo<'ONLINE' | 'OFFLINE' | 'DEGRADED'>(() => {
    if (!isOnline) return 'OFFLINE'
    return 'ONLINE'
  }, [isOnline])

  const refresh = async () => {
    if (!eventId) return
    const res = await api<{ items: BroadcastItem[] }>(`/events/${eventId}/broadcasts?limit=10`)
    setItems(res.items || [])
  }

  useEffect(() => {
    refresh().catch((e: any) => setError(e?.message ?? 'Erreur chargement broadcasts'))
  }, [eventId])

  useEffect(() => {
    if (!cooldownUntil) return
    const timer = window.setInterval(() => {
      if (Date.now() >= cooldownUntil) {
        setCooldownUntil(null)
      }
    }, 500)
    return () => window.clearInterval(timer)
  }, [cooldownUntil])

  const send = async () => {
    if (!eventId || !message.trim() || networkMode !== 'ONLINE') return
    setSending(true)
    setError(null)
    setPendingRetry(false)
    try {
      const idem = `b-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
      await api(`/partner/portal/orga/events/${eventId}/broadcast`, {
        method: 'POST',
        headers: { 'Idempotency-Key': idem },
        body: JSON.stringify({ message: message.trim(), level }),
      })
      setMessage('')
      await refresh()
    } catch (e: any) {
      setPendingRetry(true)
      if (e instanceof ApiError && e.status === 429) {
        setCooldownUntil(Date.now() + 20000)
      }
      setError(e?.message ?? 'Envoi impossible')
    } finally {
      setSending(false)
    }
  }

  const cooldownSec = cooldownUntil ? Math.max(0, Math.ceil((cooldownUntil - Date.now()) / 1000)) : 0

  return (
    <Layout title="Broadcast ORGA">
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {networkMode === 'OFFLINE' ? <InlineAlert tone="warning">OFFLINE: envoi désactivé, historique en lecture seule.</InlineAlert> : null}
      {cooldownUntil ? <InlineAlert tone="warning">Cooldown anti-spam actif: {cooldownSec}s</InlineAlert> : null}
      <Card>
        <div style={{ display: 'grid', gap: 10 }}>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value.slice(0, 240))}
            rows={4}
            placeholder="Message broadcast (240 chars max)"
          />
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <select value={level} onChange={(e) => setLevel(e.target.value as any)}>
              <option value="info">info</option>
              <option value="warn">warn</option>
              <option value="urgent">urgent</option>
            </select>
            <Button onClick={send} disabled={sending || networkMode !== 'ONLINE' || !message.trim() || !!cooldownUntil}>
              {sending ? 'Envoi…' : pendingRetry ? 'Retry send' : 'Send'}
            </Button>
            <span style={{ opacity: 0.7 }}>{message.length}/240</span>
          </div>
        </div>
      </Card>

      <Card>
        <strong>Historique (10 derniers)</strong>
        <div style={{ marginTop: 8, display: 'grid', gap: 8 }}>
          {items.map((item) => (
            <div key={item.id} style={{ border: '1px solid #2a2a2a', borderRadius: 8, padding: 8 }}>
              <div style={{ fontSize: 12, opacity: 0.75 }}>{new Date(item.created_at).toLocaleString()} · {item.level}</div>
              <div>{item.message}</div>
            </div>
          ))}
          {items.length === 0 ? <span style={{ opacity: 0.75 }}>Aucun broadcast.</span> : null}
        </div>
      </Card>
    </Layout>
  )
}
