import React, { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'
import { Badge, Button, Card, InlineAlert, Skeleton } from '../lib/ui'
import { hasBarModeAccess } from '../lib/authz'

const fields = ['orders_enabled', 'market_enabled', 'battles_enabled', 'hunt_enabled', 'polymarket_enabled', 'entry_enabled', 'checkins_enabled', 'wifi_enabled', 'safety_enabled']
const stateOptions = ['LIVE', 'PAUSE', 'MENU_ONLY', 'DEGRADED', 'FROZEN', 'CLOSED'] as const

type RuntimeState = (typeof stateOptions)[number] | 'SCHEDULED'

type Snapshot = {
  event_state: RuntimeState
  runtime_reason?: string | null
  warnings: string[]
  modules: Record<string, { configured_enabled: boolean; effective_state: 'ON' | 'OFF' | 'READ_ONLY'; reason?: string | null }>
}

type AuditItem = {
  id: number
  action: string
  created_at: string
}

function isCriticalModule(field: string) {
  return ['entry_enabled', 'checkins_enabled', 'wifi_enabled', 'safety_enabled'].includes(field)
}

export default function EventControlHub() {
  const canAccessBarMode = hasBarModeAccess()
  const { eventId } = useParams()
  const [state, setState] = useState<Record<string, boolean>>({})
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [runtimeState, setRuntimeState] = useState<RuntimeState>('LIVE')
  const [runtimeReason, setRuntimeReason] = useState('')
  const [auditItems, setAuditItems] = useState<AuditItem[]>([])
  const [savingState, setSavingState] = useState(false)
  const [savingModules, setSavingModules] = useState(false)
  const [isOnline, setIsOnline] = useState<boolean>(typeof navigator === 'undefined' ? true : navigator.onLine)
  const [error, setError] = useState<string | null>(null)
  const [mapModuleOn, setMapModuleOn] = useState(false)

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
    if (snapshot?.event_state === 'DEGRADED') return 'DEGRADED'
    return 'ONLINE'
  }, [isOnline, snapshot?.event_state])

  const canWriteModule = (field: string) => {
    if (networkMode === 'OFFLINE') return false
    if (networkMode === 'DEGRADED' && isCriticalModule(field)) return false
    return true
  }

  const refresh = async () => {
    if (!eventId) return
    const [modules, snap, audit] = await Promise.all([
      api<any>(`/partner/portal/event/${eventId}/modules`),
      api<Snapshot>(`/partner/portal/event/${eventId}/state-snapshot`),
      api<{ items: AuditItem[] }>(`/partner/portal/audit/logs?event_id=${eventId}&limit=8`),
    ])
    setState(modules)
    setSnapshot(snap)
    setRuntimeState(snap.event_state)
    setRuntimeReason(snap.runtime_reason || '')
    setAuditItems(audit.items || [])
    try {
      await api(`/events/${eventId}/map`)
      setMapModuleOn(true)
    } catch {
      setMapModuleOn(false)
    }
  }

  useEffect(() => {
    refresh().catch((e: any) => setError(e?.message ?? 'Erreur chargement ORGA HUB'))
  }, [eventId])

  const save = async () => {
    if (!eventId || networkMode === 'OFFLINE') return
    setSavingModules(true)
    setError(null)
    try {
      const payload = Object.fromEntries(fields.map((field) => [field, canWriteModule(field) ? Boolean(state[field]) : Boolean(snapshot?.modules?.[field]?.configured_enabled)]))
      const data = await api<any>(`/partner/portal/event/${eventId}/modules`, {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setState(data)
      await refresh()
    } catch (e: any) {
      setError(e?.message ?? 'Erreur sauvegarde modules')
    } finally {
      setSavingModules(false)
    }
  }

  const saveRuntime = async () => {
    if (!eventId || networkMode === 'OFFLINE') return
    if (!runtimeReason.trim()) {
      setError('Raison obligatoire pour action sensible.')
      return
    }
    setSavingState(true)
    setError(null)
    try {
      await api(`/partner/portal/event/${eventId}/state`, {
        method: 'POST',
        body: JSON.stringify({ state: runtimeState, reason: runtimeReason.trim() }),
      })
      await refresh()
    } catch (e: any) {
      setError(e?.message ?? 'Erreur changement état')
    } finally {
      setSavingState(false)
    }
  }

  return (
    <Layout title="ORGA HUB (OPS)">
      {!snapshot ? <Skeleton height={64} /> : null}
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {networkMode === 'OFFLINE' ? <InlineAlert tone="warning">OFFLINE: lecture seule. Les writes sont bloqués par le write gate global.</InlineAlert> : null}
      {networkMode === 'DEGRADED' ? <InlineAlert tone="warning">DEGRADED: les writes critiques (entry/checkins/wifi/safety) sont bloqués.</InlineAlert> : null}

      <Card>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <Badge label={`STATE ${snapshot?.event_state ?? '...'}`} tone={snapshot?.event_state === 'LIVE' ? 'success' : 'warning'} />
          <Badge label={`NET ${networkMode}`} tone={networkMode === 'ONLINE' ? 'success' : 'warning'} />
        </div>
        <div style={{ marginTop: 10, display: 'grid', gap: 8 }}>
          <strong>Event state</strong>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <select value={runtimeState} onChange={(e) => setRuntimeState(e.target.value as RuntimeState)} disabled={networkMode === 'OFFLINE'}>
              {stateOptions.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
            <input
              value={runtimeReason}
              onChange={(e) => setRuntimeReason(e.target.value)}
              placeholder="Raison obligatoire (audit)"
              style={{ minWidth: 260 }}
              disabled={networkMode === 'OFFLINE'}
            />
            <Button onClick={saveRuntime} disabled={savingState || networkMode === 'OFFLINE'}>{savingState ? 'Saving…' : 'Set state'}</Button>
          </div>
        </div>
      </Card>

      <Card>
        <strong>Cockpit</strong>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10, marginTop: 10 }}>
          <Link to="/" className="btn">Créer</Link>
          <Link to={`/event-control/${eventId}`} className="btn">Gérer live</Link>
          <Link to="/entry-staff" className="btn">Scanner entrées</Link>
          <Link to="/menu-admin" className="btn">Menu</Link>
          <Link to={`/orga/events/${eventId}/staff`} className="btn">Staff</Link>
          <Link to={`/orga/events/${eventId}/broadcast`} className="btn">Broadcast</Link>
          <Link to={`/orga/events/${eventId}/incidents`} className="btn">Incidents</Link>
          <Link to={`/orga/events/${eventId}/profitability`} className="btn">Rentabilité</Link>
          <Link to={`/orga/events/${eventId}/wifi`} className="btn">WiFi</Link>
          {mapModuleOn ? <Link to={`/orga/events/${eventId}/map`} className="btn">Carte & Navettes</Link> : null}
          {state.hunt_enabled ? <Link to={`/orga/events/${eventId}/hunts`} className="btn">Hunt</Link> : null}
          {state.battles_enabled ? <Link to={`/orga/events/${eventId}/battles`} className="btn">Battles / Affonds</Link> : null}
          {canAccessBarMode ? (
            <>
              <Link to={`/bar/events/${eventId}/dashboard`} className="btn">BAR MODE · Dashboard</Link>
              <Link to="/orders-queue" className="btn">BAR MODE · Orders Live</Link>
              <Link to="/menu-admin" className="btn">BAR MODE · Menu Admin</Link>
              <Link to="/analytics" className="btn">BAR MODE · Analytics</Link>
            </>
          ) : null}
          <Link to={`/audit/${eventId}`} className="btn">Logs</Link>
          {state.safety_enabled ? <Link to={`/orga/events/${eventId}/safety`} className="btn">Safe Kit</Link> : null}
        </div>
      </Card>

      {fields.map((field) => (
        <label key={field} style={{ display: 'block', marginBottom: 8 }}>
          <input
            type="checkbox"
            checked={!!state[field]}
            onChange={(e) => setState((prev) => ({ ...prev, [field]: e.target.checked }))}
            disabled={!canWriteModule(field)}
          />{' '}
          {field}
          {snapshot?.modules?.[field] ? <span style={{ marginLeft: 8, opacity: 0.75 }}>({snapshot.modules[field].effective_state}{snapshot.modules[field].reason ? `/${snapshot.modules[field].reason}` : ''})</span> : null}
        </label>
      ))}
      <Button onClick={save} disabled={savingModules || networkMode === 'OFFLINE'}>{savingModules ? 'Saving…' : 'Save toggles'}</Button>

      <div style={{ marginTop: 14 }}>
        <Card>
          <strong>Audit récent</strong>
          <div style={{ display: 'grid', gap: 6, marginTop: 8 }}>
            {auditItems.map((item) => (
              <div key={item.id} style={{ fontSize: 14 }}>
                [{new Date(item.created_at).toLocaleTimeString()}] {item.action}
              </div>
            ))}
            {auditItems.length === 0 ? <span style={{ opacity: 0.75 }}>Aucun audit.</span> : null}
          </div>
        </Card>
      </div>
    </Layout>
  )
}
