import React, { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'
import { Button, Card, InlineAlert } from '../lib/ui'

type WifiTokenItem = {
  id: number
  tokenId: string
  createdAt: string
  expiresAt: string
  revokedAt?: string | null
  status: 'active' | 'expired' | 'revoked'
  revokeReason?: string | null
}

type WifiSnapshot = {
  enabled: boolean
  ssid: string
  hasPassword: boolean
  instructions?: string | null
  tokenStats: { active: number; revoked: number; expired: number }
  tokens: WifiTokenItem[]
}

export default function WifiAdmin() {
  const { eventId } = useParams()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [snapshot, setSnapshot] = useState<WifiSnapshot | null>(null)
  const [enabled, setEnabled] = useState(false)
  const [ssid, setSsid] = useState('')
  const [password, setPassword] = useState('')
  const [instructions, setInstructions] = useState('')
  const [tokenTtl, setTokenTtl] = useState(3600)
  const [generatedRaw, setGeneratedRaw] = useState('')
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

  const readOnly = useMemo(() => !isOnline, [isOnline])

  const refresh = async () => {
    if (!eventId) return
    setLoading(true)
    setError(null)
    try {
      const data = await api<WifiSnapshot>(`/partner/portal/orga/events/${eventId}/wifi`)
      setSnapshot(data)
      setEnabled(Boolean(data.enabled))
      setSsid(data.ssid || '')
      setInstructions(data.instructions || '')
      setPassword('')
    } catch (e: any) {
      setError(e?.message ?? 'Erreur chargement WiFi')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [eventId])

  const saveSettings = async () => {
    if (!eventId || readOnly) return
    setError(null)
    try {
      await api(`/partner/portal/orga/events/${eventId}/wifi`, {
        method: 'PUT',
        headers: { 'Idempotency-Key': `wifi-settings-${eventId}-${Date.now()}` },
        body: JSON.stringify({ enabled, ssid, password: password || undefined, instructions }),
      })
      await refresh()
    } catch (e: any) {
      setError(e?.message ?? 'Erreur sauvegarde WiFi')
    }
  }

  const generateToken = async () => {
    if (!eventId || readOnly) return
    setError(null)
    try {
      const data = await api<any>(`/partner/portal/orga/events/${eventId}/wifi/tokens`, {
        method: 'POST',
        headers: { 'Idempotency-Key': `wifi-token-${eventId}-${Date.now()}` },
        body: JSON.stringify({ ttlSeconds: tokenTtl }),
      })
      setGeneratedRaw((data?.qr?.raw ?? '').toString())
      await refresh()
    } catch (e: any) {
      setError(e?.message ?? 'Erreur génération token')
    }
  }

  const revokeToken = async (tokenId: string) => {
    if (!eventId || readOnly) return
    await api(`/partner/portal/orga/events/${eventId}/wifi/tokens/${tokenId}/revoke`, {
      method: 'POST',
      headers: { 'Idempotency-Key': `wifi-revoke-${eventId}-${tokenId}-${Date.now()}` },
      body: JSON.stringify({ reason: 'manual revoke' }),
    })
    await refresh()
  }

  return (
    <Layout title="Event WiFi">
      <Card>
        <Link to={`/event-control/${eventId}`} className="btn">← ORGA HUB</Link>
      </Card>

      {readOnly ? <InlineAlert tone="warning">Mode lecture OFFLINE : génération/revoke indisponibles, cache visible.</InlineAlert> : null}
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}

      <Card>
        <h3>Configuration WiFi</h3>
        {loading ? <div>Chargement...</div> : null}
        <label><input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} disabled={readOnly} /> Module WiFi activé</label>
        <div><input value={ssid} onChange={(e) => setSsid(e.target.value)} placeholder="SSID" disabled={readOnly} /></div>
        <div><input value={password} onChange={(e) => setPassword(e.target.value)} placeholder={snapshot?.hasPassword ? 'Nouveau mot de passe (optionnel)' : 'Mot de passe'} disabled={readOnly} /></div>
        <div><textarea value={instructions} onChange={(e) => setInstructions(e.target.value)} placeholder="Instructions" disabled={readOnly} /></div>
        <Button onClick={saveSettings} disabled={readOnly}>Enregistrer</Button>
      </Card>

      <Card>
        <h3>QR token WiFi</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <select value={tokenTtl} onChange={(e) => setTokenTtl(Number(e.target.value))} disabled={readOnly}>
            <option value={1800}>30 min</option>
            <option value={3600}>1 h</option>
            <option value={21600}>6 h</option>
            <option value={43200}>12 h</option>
          </select>
          <Button onClick={generateToken} disabled={readOnly || !enabled}>Generate QR token</Button>
        </div>
        {generatedRaw ? <pre style={{ whiteSpace: 'pre-wrap' }}>{generatedRaw}</pre> : null}
      </Card>

      <Card>
        <h3>Tokens récents</h3>
        <div>Active: {snapshot?.tokenStats.active ?? 0} • Revoked: {snapshot?.tokenStats.revoked ?? 0} • Expired: {snapshot?.tokenStats.expired ?? 0}</div>
        <ul>
          {(snapshot?.tokens ?? []).map((t) => (
            <li key={t.id}>
              #{t.id} — {t.status} — expire {new Date(t.expiresAt).toLocaleString()}
              {t.status === 'active' ? <Button onClick={() => revokeToken(t.tokenId)} disabled={readOnly}>Revoke</Button> : null}
            </li>
          ))}
        </ul>
      </Card>
    </Layout>
  )
}
