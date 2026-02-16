import React, { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'
import { Button, Card, InlineAlert } from '../lib/ui'

type AlertItem = {
  id: number
  userId: string
  type: 'PANIC'
  createdAt: string
  assignedToUserId?: number | null
  resolvedAt?: string | null
  resolveReason?: string | null
}

type CheckinItem = {
  id: number
  userId: string
  type: 'OK' | 'PANIC'
  createdAt: string
}

export default function OrgaEventSafety() {
  const { eventId } = useParams()
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [recent, setRecent] = useState<CheckinItem[]>([])
  const [orgaPhone, setOrgaPhone] = useState('')
  const [messageHint, setMessageHint] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isOnline, setIsOnline] = useState<boolean>(typeof navigator === 'undefined' ? true : navigator.onLine)
  const [runtimeState, setRuntimeState] = useState('LIVE')

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

  const networkMode = useMemo<'ONLINE' | 'DEGRADED' | 'OFFLINE'>(() => {
    if (!isOnline) return 'OFFLINE'
    if (runtimeState === 'DEGRADED') return 'DEGRADED'
    return 'ONLINE'
  }, [isOnline, runtimeState])

  const writesBlocked = networkMode !== 'ONLINE'

  const refresh = async () => {
    if (!eventId) return
    const [state, settings, payload] = await Promise.all([
      api<any>(`/partner/portal/event/${eventId}/state-snapshot`),
      api<any>(`/partner/portal/orga/events/${eventId}/safety/settings`),
      api<any>(`/partner/portal/orga/events/${eventId}/safety/alerts?status=open`),
    ])
    setRuntimeState(state?.event_state || 'LIVE')
    setEnabled(settings?.enabled !== false)
    setOrgaPhone(settings?.orgaPhone || '')
    setMessageHint(settings?.messageHint || '')
    setAlerts(payload?.alerts || [])
    setRecent(payload?.recentCheckins || [])
  }

  useEffect(() => {
    refresh().catch((e: any) => setError(e?.message || 'Erreur Safe Kit'))
  }, [eventId])

  useEffect(() => {
    if (!eventId || networkMode === 'OFFLINE') return
    const periodMs = networkMode === 'DEGRADED' ? 6000 : 3000
    const timer = setInterval(() => {
      refresh().catch(() => {})
    }, periodMs)
    return () => clearInterval(timer)
  }, [eventId, networkMode])

  const saveSettings = async () => {
    if (!eventId || writesBlocked) return
    setError(null)
    try {
      await api(`/partner/portal/orga/events/${eventId}/safety/settings`, {
        method: 'PUT',
        headers: { 'Idempotency-Key': `safety-settings-${eventId}-${Date.now()}` },
        body: JSON.stringify({ enabled, orgaPhone, messageHint }),
      })
      await refresh()
    } catch (e: any) {
      setError(e?.message || 'Erreur settings safety')
    }
  }

  const assignAlert = async (id: number) => {
    if (!eventId || writesBlocked) return
    await api(`/partner/portal/orga/events/${eventId}/safety/alerts/${id}/assign`, {
      method: 'POST',
      headers: { 'Idempotency-Key': `safety-assign-${id}-${Date.now()}` },
      body: JSON.stringify({}),
    })
    await refresh()
  }

  const resolveAlert = async (id: number) => {
    if (!eventId || writesBlocked) return
    const reason = window.prompt('Raison de résolution', 'Pris en charge par orga')
    if (!reason) return
    await api(`/partner/portal/orga/events/${eventId}/safety/alerts/${id}/resolve`, {
      method: 'POST',
      headers: { 'Idempotency-Key': `safety-resolve-${id}-${Date.now()}` },
      body: JSON.stringify({ reason }),
    })
    await refresh()
  }

  const exportCsv = () => {
    if (!eventId) return
    window.open(`${window.location.origin}/partner/portal/orga/events/${eventId}/safety/export.csv`, '_blank')
  }

  const exportJson = () => {
    if (!eventId) return
    window.open(`${window.location.origin}/partner/portal/orga/events/${eventId}/safety/export.json`, '_blank')
  }

  return (
    <Layout title="ORGA Safe Kit">
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {networkMode === 'OFFLINE' ? <InlineAlert tone="warning">OFFLINE: lecture seule.</InlineAlert> : null}
      {networkMode === 'DEGRADED' ? <InlineAlert tone="warning">DEGRADED: writes critiques Safe Kit bloqués.</InlineAlert> : null}

      <Card>
        <h3>Settings</h3>
        <label style={{ display: 'block', marginBottom: 8 }}><input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} disabled={writesBlocked} /> Module activé</label>
        <input value={orgaPhone} onChange={(e) => setOrgaPhone(e.target.value)} placeholder="Numéro orga safety" style={{ width: '100%', marginBottom: 8 }} disabled={writesBlocked} />
        <textarea value={messageHint} onChange={(e) => setMessageHint(e.target.value)} placeholder="Message d'aide" style={{ width: '100%', minHeight: 70, marginBottom: 8 }} disabled={writesBlocked} />
        <Button onClick={saveSettings} disabled={writesBlocked}>Sauvegarder</Button>
      </Card>

      <Card>
        <h3>Alertes ouvertes (PANIC)</h3>
        {alerts.length === 0 ? <p>Aucune alerte ouverte.</p> : alerts.map((alert) => (
          <div key={alert.id} style={{ borderTop: '1px solid rgba(255,255,255,0.1)', padding: '8px 0' }}>
            <div><strong>#{alert.id}</strong> · user {alert.userId} · {new Date(alert.createdAt).toLocaleString()}</div>
            <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
              <Button onClick={() => assignAlert(alert.id)} disabled={writesBlocked}>Assigner</Button>
              <Button onClick={() => resolveAlert(alert.id)} disabled={writesBlocked}>Résoudre</Button>
            </div>
          </div>
        ))}
      </Card>

      <Card>
        <h3>Feed check-ins récents</h3>
        {recent.slice(0, 20).map((item) => (
          <div key={item.id} style={{ fontSize: 14, marginBottom: 6 }}>
            [{new Date(item.createdAt).toLocaleTimeString()}] {item.type} · user {item.userId}
          </div>
        ))}
      </Card>

      <Card>
        <h3>Exports</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button onClick={exportCsv}>Export CSV</Button>
          <Button onClick={exportJson}>Export JSON</Button>
        </div>
      </Card>
    </Layout>
  )
}
