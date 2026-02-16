import React, { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'
import { Button, Card, InlineAlert } from '../lib/ui'

type MapSettings = {
  enabled: boolean
  venueName?: string | null
  address?: string | null
  lat?: number | null
  lng?: number | null
  tecLink?: string | null
  wazeLink?: string | null
  navettes: {
    enabled: boolean
    address?: string | null
    lastReturnTime?: string | null
    notes?: string | null
  }
}

export default function OrgaEventMap() {
  const { eventId } = useParams()
  const [settings, setSettings] = useState<MapSettings>({ enabled: false, navettes: { enabled: false } })
  const [runtimeState, setRuntimeState] = useState('LIVE')
  const [isOnline, setIsOnline] = useState<boolean>(typeof navigator === 'undefined' ? true : navigator.onLine)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const writeBlocked = useMemo(() => !isOnline || runtimeState === 'FROZEN' || runtimeState === 'CLOSED', [isOnline, runtimeState])

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
    const [map, snapshot] = await Promise.all([
      api<Partial<MapSettings>>(`/partner/portal/orga/events/${eventId}/map/settings`),
      api<{ event_state?: string }>(`/partner/portal/event/${eventId}/state-snapshot`),
    ])
    setSettings({ enabled: Boolean(map.enabled), ...map, navettes: { enabled: false, ...(map.navettes || {}) } })
    setRuntimeState((snapshot.event_state || 'LIVE').toUpperCase())
  }

  useEffect(() => {
    refresh().catch((e: any) => setError(e?.message ?? 'Erreur chargement carte/navettes'))
  }, [eventId])

  const save = async () => {
    if (!eventId || writeBlocked) return
    setSaving(true)
    setError(null)
    try {
      await api(`/partner/portal/orga/events/${eventId}/map/settings`, {
        method: 'PUT',
        headers: { 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify(settings),
      })
      await refresh()
    } catch (e: any) {
      setError(e?.message ?? 'Erreur sauvegarde')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Layout title="Carte & Navettes">
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {!isOnline ? <InlineAlert tone="warning">OFFLINE: lecture seule.</InlineAlert> : null}
      {runtimeState === 'FROZEN' || runtimeState === 'CLOSED' ? <InlineAlert tone="warning">Writes bloqués en runtime {runtimeState}.</InlineAlert> : null}

      <Card>
        <strong>Réglages carte</strong>
        <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
          <label><input type="checkbox" checked={!!settings.enabled} disabled={writeBlocked} onChange={(e) => setSettings((p) => ({ ...p, enabled: e.target.checked }))} /> Activer module carte</label>
          <input placeholder="Nom du lieu" value={settings.venueName ?? ''} disabled={writeBlocked} onChange={(e) => setSettings((p) => ({ ...p, venueName: e.target.value }))} />
          <input placeholder="Adresse" value={settings.address ?? ''} disabled={writeBlocked} onChange={(e) => setSettings((p) => ({ ...p, address: e.target.value }))} />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <input type="number" step="any" placeholder="Latitude" value={settings.lat ?? ''} disabled={writeBlocked} onChange={(e) => setSettings((p) => ({ ...p, lat: e.target.value ? Number(e.target.value) : null }))} />
            <input type="number" step="any" placeholder="Longitude" value={settings.lng ?? ''} disabled={writeBlocked} onChange={(e) => setSettings((p) => ({ ...p, lng: e.target.value ? Number(e.target.value) : null }))} />
          </div>
          <input placeholder="Lien TEC" value={settings.tecLink ?? ''} disabled={writeBlocked} onChange={(e) => setSettings((p) => ({ ...p, tecLink: e.target.value }))} />
          <input placeholder="Lien Waze" value={settings.wazeLink ?? ''} disabled={writeBlocked} onChange={(e) => setSettings((p) => ({ ...p, wazeLink: e.target.value }))} />
        </div>
      </Card>

      <Card>
        <strong>Navettes</strong>
        <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
          <label><input type="checkbox" checked={!!settings.navettes?.enabled} disabled={writeBlocked} onChange={(e) => setSettings((p) => ({ ...p, navettes: { ...(p.navettes || {}), enabled: e.target.checked } }))} /> Activer navettes</label>
          <input placeholder="Adresse navettes" value={settings.navettes?.address ?? ''} disabled={writeBlocked} onChange={(e) => setSettings((p) => ({ ...p, navettes: { ...(p.navettes || {}), address: e.target.value } }))} />
          <input placeholder="Dernier retour (HH:mm)" value={settings.navettes?.lastReturnTime ?? ''} disabled={writeBlocked} onChange={(e) => setSettings((p) => ({ ...p, navettes: { ...(p.navettes || {}), lastReturnTime: e.target.value } }))} />
          <textarea placeholder="Notes" value={settings.navettes?.notes ?? ''} disabled={writeBlocked} onChange={(e) => setSettings((p) => ({ ...p, navettes: { ...(p.navettes || {}), notes: e.target.value } }))} />
        </div>
      </Card>

      <Card>
        <strong>Preview</strong>
        <div style={{ marginTop: 10, opacity: 0.85 }}>
          <div>{settings.venueName || 'Lieu event'}</div>
          <div>{settings.address || 'Adresse non renseignée'}</div>
          <div>{settings.lat && settings.lng ? `${settings.lat}, ${settings.lng}` : 'Coordonnées non renseignées'}</div>
          {settings.navettes?.enabled ? <div>Navettes: {settings.navettes.address || '—'} · Dernier retour {settings.navettes.lastReturnTime || '—'}</div> : null}
        </div>
      </Card>

      <Button disabled={saving || writeBlocked} onClick={save}>{saving ? 'Saving…' : 'Enregistrer'}</Button>
    </Layout>
  )
}
