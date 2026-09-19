import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { API_BASE, api } from '../lib/api'
import { getToken } from '../lib/auth'
import { Badge, Button, Card, EmptyState, InlineAlert } from '../lib/ui'
import { clearIncidentDraft, loadIncidentDraft, saveIncidentDraft, type IncidentDraft } from '../lib/incidentDraft'

type Incident = {
  id: number
  title?: string | null
  description: string
  severity: 'info' | 'warn' | 'critical'
  status: 'open' | 'assigned' | 'resolved' | 'canceled'
  location?: string | null
  assignedLabel?: string | null
  createdAt: string
}

type IncidentLog = { id: number; actionType: string; actor: string; payload: Record<string, unknown>; createdAt: string }
type StaffAssignment = { id: number; role: string; label?: string | null; status: string }

function toneForSeverity(sev: Incident['severity']) {
  if (sev === 'critical') return 'danger'
  if (sev === 'warn') return 'warning'
  return 'neutral'
}

export default function OrgaIncidents() {
  const { eventId } = useParams()
  const [items, setItems] = useState<Incident[]>([])
  const [selected, setSelected] = useState<Incident | null>(null)
  const [logs, setLogs] = useState<IncidentLog[]>([])
  const [staff, setStaff] = useState<StaffAssignment[]>([])
  const [showNew, setShowNew] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isOnline, setIsOnline] = useState<boolean>(typeof navigator === 'undefined' ? true : navigator.onLine)

  const emptyDraft = (): IncidentDraft => ({ severity: 'warn', description: '', location: '', title: '' })
  const [draft, setDraft] = useState<IncidentDraft>(() => loadIncidentDraft(eventId) ?? emptyDraft())
  const skipNextDraftSave = useRef(false)

  useEffect(() => {
    skipNextDraftSave.current = true
    setDraft(loadIncidentDraft(eventId) ?? emptyDraft())
  }, [eventId])

  useEffect(() => {
    if (skipNextDraftSave.current) {
      skipNextDraftSave.current = false
      return
    }
    saveIncidentDraft(eventId, draft)
  }, [eventId, draft])

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

  const networkMode = useMemo<'ONLINE' | 'OFFLINE'>(() => (isOnline ? 'ONLINE' : 'OFFLINE'), [isOnline])

  const refresh = async () => {
    if (!eventId) return
    const [incidentRes, staffRes] = await Promise.all([
      api<{ items: Incident[] }>(`/partner/portal/orga/events/${eventId}/incidents`),
      api<{ items: StaffAssignment[] }>(`/partner/portal/orga/events/${eventId}/staff`),
    ])
    setItems(incidentRes.items || [])
    setStaff((staffRes.items || []).filter((s) => s.status === 'ACTIVE'))
  }

  const loadLogs = async (incidentId: number) => {
    const res = await api<{ items: IncidentLog[] }>(`/partner/portal/orga/incidents/${incidentId}/logs`)
    setLogs(res.items || [])
  }

  useEffect(() => {
    refresh().catch((e: any) => setError(e?.message ?? 'Erreur chargement incidents'))
    const timer = window.setInterval(() => {
      refresh().catch(() => undefined)
      if (selected) loadLogs(selected.id).catch(() => undefined)
    }, 5000)
    return () => window.clearInterval(timer)
  }, [eventId, selected?.id])

  const createIncident = async () => {
    if (!eventId || !draft.description.trim() || networkMode !== 'ONLINE') return
    setSaving(true)
    setError(null)
    try {
      await api(`/partner/portal/orga/events/${eventId}/incidents`, {
        method: 'POST',
        headers: { 'Idempotency-Key': `incident-create-${eventId}-${Date.now()}` },
        body: JSON.stringify({ ...draft, description: draft.description.trim(), location: draft.location || undefined, title: draft.title || undefined }),
      })
      setShowNew(false)
      skipNextDraftSave.current = true
      clearIncidentDraft(eventId)
      setDraft(emptyDraft())
      await refresh()
    } catch (e: any) {
      setError(e?.message ?? 'Erreur création incident')
    } finally {
      setSaving(false)
    }
  }

  const actionOnSelected = async (path: string, body: Record<string, unknown>) => {
    if (!selected || networkMode !== 'ONLINE') return
    setSaving(true)
    setError(null)
    try {
      await api(`/partner/portal/orga/incidents/${selected.id}/${path}`, {
        method: 'POST',
        headers: { 'Idempotency-Key': `incident-${path}-${selected.id}-${Date.now()}` },
        body: JSON.stringify(body),
      })
      await refresh()
      await loadLogs(selected.id)
    } catch (e: any) {
      setError(e?.message ?? `Erreur ${path}`)
    } finally {
      setSaving(false)
    }
  }

  const exportDossier = async () => {
    if (!eventId) return
    const token = getToken()
    const res = await fetch(`${API_BASE}/partner/portal/orga/events/${eventId}/incidents/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) {
      setError(`Export impossible (HTTP ${res.status})`)
      return
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `incidents-event-${eventId}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Layout title="ORGA Incidents">
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {networkMode === 'OFFLINE' ? <InlineAlert tone="warning">OFFLINE: écritures désactivées, lecture seule.</InlineAlert> : null}
      <Card>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Badge label={`NET ${networkMode}`} tone={networkMode === 'ONLINE' ? 'success' : 'warning'} />
          <Button onClick={() => setShowNew(true)} disabled={networkMode !== 'ONLINE'}>New incident</Button>
          <Button variant="secondary" onClick={exportDossier}>Export dossier</Button>
        </div>
      </Card>

      {showNew ? (
        <Card>
          <strong>Nouveau incident</strong>
          <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
            <select value={draft.severity} onChange={(e) => setDraft((prev) => ({ ...prev, severity: e.target.value as IncidentDraft['severity'] }))}>
              <option value="info">INFO</option><option value="warn">WARN</option><option value="critical">CRITICAL</option>
            </select>
            <input value={draft.title} onChange={(e) => setDraft((prev) => ({ ...prev, title: e.target.value }))} placeholder="Titre (optionnel)" />
            <textarea value={draft.description} onChange={(e) => setDraft((prev) => ({ ...prev, description: e.target.value }))} placeholder="Description (requis)" rows={3} />
            <input value={draft.location} onChange={(e) => setDraft((prev) => ({ ...prev, location: e.target.value }))} placeholder="Localisation (optionnel)" />
            <div style={{ display: 'flex', gap: 8 }}>
              <Button onClick={createIncident} disabled={saving || !draft.description.trim() || networkMode !== 'ONLINE'}>{saving ? 'Pending…' : 'Créer'}</Button>
              <Button variant="secondary" onClick={() => setShowNew(false)}>Cancel</Button>
            </div>
          </div>
        </Card>
      ) : null}

      <Card>
        <strong>Incidents</strong>
        {items.length === 0 ? <EmptyState title="Aucun incident" body="Créer un incident pour démarrer le suivi terrain." /> : null}
        <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
          {items.map((item) => (
            <button key={item.id} onClick={() => { setSelected(item); loadLogs(item.id).catch(() => undefined) }} style={{ textAlign: 'left', padding: 10 }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <strong>#{item.id} {item.title || 'Incident'}</strong>
                <Badge label={item.severity.toUpperCase()} tone={toneForSeverity(item.severity) as any} />
                <Badge label={item.status.toUpperCase()} tone={item.status === 'resolved' ? 'success' : 'warning'} />
              </div>
              <div style={{ opacity: 0.9 }}>{item.description}</div>
              <div style={{ opacity: 0.7, fontSize: 12 }}>{item.location || 'location n/a'} • {item.assignedLabel || 'non assigné'}</div>
            </button>
          ))}
        </div>
      </Card>

      {selected ? (
        <Card>
          <strong>Détail incident #{selected.id}</strong>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
            <select onChange={(e) => actionOnSelected('assign', { assignmentId: Number(e.target.value), reason: 'assign from UI' })} defaultValue="">
              <option value="">Assigner à staff…</option>
              {staff.map((item) => <option key={item.id} value={item.id}>{item.label || item.role}</option>)}
            </select>
            <Button variant="secondary" onClick={() => actionOnSelected('assign', { role: 'MANAGER', reason: 'fallback role' })}>Assign role MANAGER</Button>
            <Button onClick={() => {
              const reason = window.prompt('Raison escalade ?') || ''
              if (!reason.trim()) return
              actionOnSelected('escalate', { severity: 'critical', reason })
            }} disabled={networkMode !== 'ONLINE'}>Escalate critical</Button>
            <Button variant="secondary" onClick={() => actionOnSelected('set_status', { status: 'resolved', reason: 'resolved from UI' })} disabled={networkMode !== 'ONLINE'}>Resolve</Button>
            <Button variant="secondary" onClick={() => actionOnSelected('set_status', { status: 'canceled', reason: 'canceled from UI' })} disabled={networkMode !== 'ONLINE'}>Cancel</Button>
          </div>

          <div style={{ marginTop: 12, display: 'grid', gap: 6 }}>
            {logs.map((row) => (
              <div key={row.id} style={{ fontSize: 14 }}>
                [{new Date(row.createdAt).toLocaleTimeString()}] <strong>{row.actionType}</strong> — {row.actor}
              </div>
            ))}
            {logs.length === 0 ? <span style={{ opacity: 0.7 }}>No logs.</span> : null}
          </div>
        </Card>
      ) : null}
    </Layout>
  )
}
