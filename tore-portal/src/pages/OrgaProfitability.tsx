import React, { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api, API_BASE } from '../lib/api'
import { getToken } from '../lib/auth'
import { Button, Card, InlineAlert } from '../lib/ui'

type Profitability = {
  ordersCount: number
  itemsCount: number
  grossRevenueTickets: number
  grossRevenueEuro: number | null
  avgOrderValueTickets: number
  lastUpdatedAt: string
  costs: {
    costsTickets: number
    notes?: string | null
    breakdown?: Record<string, unknown>
    updatedBy?: string | null
    updatedAt?: string | null
  }
  netEstimateTickets: number
}

export default function OrgaProfitability() {
  const { eventId } = useParams()
  const [data, setData] = useState<Profitability | null>(null)
  const [costsTickets, setCostsTickets] = useState<string>('0')
  const [notes, setNotes] = useState<string>('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isOnline, setIsOnline] = useState<boolean>(typeof navigator === 'undefined' ? true : navigator.onLine)
  const [eventState, setEventState] = useState<string>('LIVE')

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
    const [profitability, snapshot] = await Promise.all([
      api<Profitability>(`/partner/portal/orga/events/${eventId}/profitability`),
      api<{ event_state: string }>(`/partner/portal/event/${eventId}/state-snapshot`),
    ])
    setData(profitability)
    setEventState(snapshot.event_state)
    setCostsTickets(String(profitability.costs?.costsTickets ?? 0))
    setNotes(profitability.costs?.notes || '')
  }

  useEffect(() => {
    refresh().catch((e: any) => setError(e?.message ?? 'Erreur chargement rentabilité'))
    const timer = window.setInterval(() => {
      refresh().catch(() => null)
    }, 5000)
    return () => window.clearInterval(timer)
  }, [eventId])

  const networkMode = useMemo<'ONLINE' | 'OFFLINE' | 'DEGRADED'>(() => {
    if (!isOnline) return 'OFFLINE'
    if (eventState === 'DEGRADED') return 'DEGRADED'
    return 'ONLINE'
  }, [isOnline, eventState])

  const saveDisabledReason = useMemo(() => {
    if (networkMode === 'OFFLINE') return 'Write gate: offline'
    if (networkMode === 'DEGRADED') return 'Write gate: event runtime degraded'
    return null
  }, [networkMode])

  const saveCosts = async () => {
    if (!eventId || saveDisabledReason) return
    setSaving(true)
    setError(null)
    try {
      const idem = `profitability-costs-${eventId}-${Date.now()}`
      const payload = await api<Profitability>(`/partner/portal/orga/events/${eventId}/costs`, {
        method: 'PUT',
        headers: { 'Idempotency-Key': idem },
        body: JSON.stringify({ costsTickets: Math.max(0, Number(costsTickets) || 0), notes: notes.trim() || null }),
      })
      setData(payload)
    } catch (e: any) {
      setError(e?.message ?? 'Erreur sauvegarde coûts')
    } finally {
      setSaving(false)
    }
  }

  const exportCsv = async () => {
    if (!eventId) return
    const res = await fetch(`${API_BASE}/partner/portal/orga/events/${eventId}/profitability/export.csv`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    if (!res.ok) {
      const body = await res.text()
      throw new Error(body || `HTTP ${res.status}`)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `profitability_event_${eventId}.csv`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const exportJson = async () => {
    if (!eventId) return
    const res = await fetch(`${API_BASE}/partner/portal/orga/events/${eventId}/profitability/export.json`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    if (!res.ok) {
      const body = await res.text()
      throw new Error(body || `HTTP ${res.status}`)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `profitability_event_${eventId}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Layout title="Rentabilité live">
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {saveDisabledReason ? <InlineAlert tone="warning">{saveDisabledReason}</InlineAlert> : null}

      <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
        <Card><strong>CA (tickets)</strong><div style={{ fontSize: 24 }}>{data?.grossRevenueTickets ?? 0}</div></Card>
        <Card><strong>Orders</strong><div style={{ fontSize: 24 }}>{data?.ordersCount ?? 0}</div></Card>
        <Card><strong>Panier moyen</strong><div style={{ fontSize: 24 }}>{(data?.avgOrderValueTickets ?? 0).toFixed(2)}</div></Card>
        <Card><strong>Coûts</strong><div style={{ fontSize: 24 }}>{data?.costs?.costsTickets ?? 0}</div></Card>
        <Card><strong>Net estimé</strong><div style={{ fontSize: 24 }}>{data?.netEstimateTickets ?? 0}</div></Card>
      </div>

      <Card>
        <strong>Costs (simple)</strong>
        <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
          <label>
            coûtsTickets
            <input type="number" min={0} value={costsTickets} onChange={(e) => setCostsTickets(e.target.value)} disabled={Boolean(saveDisabledReason)} />
          </label>
          <label>
            Notes (optionnel)
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} disabled={Boolean(saveDisabledReason)} rows={3} />
          </label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Button onClick={saveCosts} disabled={saving || Boolean(saveDisabledReason)}>{saving ? 'Saving…' : 'Save costs'}</Button>
            <Button onClick={() => exportCsv().catch((e: any) => setError(e?.message ?? 'Export CSV impossible'))}>Export CSV</Button>
            <Button onClick={() => exportJson().catch((e: any) => setError(e?.message ?? 'Export JSON impossible'))}>Export JSON</Button>
          </div>
          <div style={{ opacity: 0.7, fontSize: 13 }}>
            Last update: {data?.costs?.updatedAt ? new Date(data.costs.updatedAt).toLocaleString() : 'n/a'} {data?.costs?.updatedBy ? `• by ${data.costs.updatedBy}` : ''}
          </div>
        </div>
      </Card>
    </Layout>
  )
}
