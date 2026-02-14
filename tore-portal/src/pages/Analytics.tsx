import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout, { btn, cardStyle, inputStyle } from '../ui/Layout'
import { api, API_BASE } from '../lib/api'
import { getToken } from '../lib/auth'

type EventOut = {
  id: number
  name: string
}

type AnalyticsSummary = {
  orders: {
    count: number
    total_cents: number
    paid_count: number
    unpaid_count: number
    paid_tickets_total: number
  }
  menu: {
    top_items: Array<{
      item_id: number | null
      name: string
      views: number
      adds: number
    }>
    totals: {
      views: number
      adds: number
    }
  }
  polymarket: {
    bets_live: number
    bets_pending: number
    bets_finalized: number
    total_staked_tickets: number
    total_payout_tickets: number
  }
}

function euro(cents: number): string {
  return (cents / 100).toLocaleString('fr-BE', { style: 'currency', currency: 'EUR' })
}

export default function Analytics() {
  const [events, setEvents] = useState<EventOut[]>([])
  const [days, setDays] = useState(7)
  const [eventId, setEventId] = useState<number | ''>('')
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [exportLoading, setExportLoading] = useState<string>('')
  const [exportError, setExportError] = useState<string | null>(null)
  const [barIdentityConsent, setBarIdentityConsent] = useState(false)
  const [consentBusy, setConsentBusy] = useState(false)
  const [consentMessage, setConsentMessage] = useState<string | null>(null)

  const query = useMemo(() => {
    const qs = new URLSearchParams({ days: String(days) })
    if (eventId !== '') qs.set('event_id', String(eventId))
    return qs.toString()
  }, [days, eventId])

  const downloadCsv = async (path: string, filename: string, key: string) => {
    const token = getToken()
    if (!token) return
    setExportLoading(key)
    setExportError(null)
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        const body = await res.text()
        throw new Error(body || `HTTP ${res.status}`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      setExportError(e?.message || 'Export impossible')
    } finally {
      setExportLoading('')
    }
  }

  useEffect(() => {
    ;(async () => {
      try {
        const rows = await api<EventOut[]>('/partner/portal/events')
        setEvents(rows)
      } catch {
        setEvents([])
      }
      try {
        const settings = await api<{ staff_identity_consent_required: boolean }>('/partner/portal/settings/identity-consent')
        setBarIdentityConsent(Boolean(settings.staff_identity_consent_required))
      } catch {
        setBarIdentityConsent(false)
      }
    })()
  }, [])

  useEffect(() => {
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await api<AnalyticsSummary>(`/partner/portal/analytics/summary?${query}`)
        setSummary(data)
      } catch (e: any) {
        setError(e?.message ?? 'Impossible de charger les analytics')
      } finally {
        setLoading(false)
      }
    })()
  }, [query])

  const patchConsent = async (next: boolean) => {
    setConsentBusy(true)
    setConsentMessage(null)
    try {
      const saved = await api<{ staff_identity_consent_required: boolean }>('/partner/portal/settings/identity-consent', {
        method: 'PATCH',
        body: JSON.stringify({ staff_identity_consent_required: next }),
      })
      setBarIdentityConsent(Boolean(saved.staff_identity_consent_required))
      setConsentMessage('Paramètre sauvegardé.')
    } catch (e: any) {
      setConsentMessage(e?.message || 'Impossible de sauvegarder le paramètre.')
    } finally {
      setConsentBusy(false)
    }
  }

  return (
    <Layout title="Ops Dashboard V1">
      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        <Link to="/" style={{ ...btn('ghost'), textDecoration: 'none' }}>← Dashboard</Link>
      </div>

      <div style={{ ...cardStyle(), display: 'grid', gap: 10, marginBottom: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto auto', gap: 10 }}>
          <label>
            <div style={{ marginBottom: 6 }}>Période (jours)</div>
            <input
              type="number"
              min={1}
              max={90}
              value={days}
              onChange={(e) => setDays(Math.max(1, Math.min(90, Number(e.target.value) || 7)))}
              style={inputStyle()}
            />
          </label>
          <label>
            <div style={{ marginBottom: 6 }}>Event</div>
            <select value={eventId} onChange={(e) => setEventId(e.target.value ? Number(e.target.value) : '')} style={inputStyle()}>
              <option value="">Tous</option>
              {events.map((ev) => (
                <option key={ev.id} value={ev.id}>{ev.name}</option>
              ))}
            </select>
          </label>
          <div style={{ display: 'flex', alignItems: 'end' }}>
            <button
              type="button"
              onClick={() => void downloadCsv(`/partner/portal/analytics/orders.csv?${query}`, `orders-${days}d.csv`, 'orders')}
              style={btn('ghost')}
              disabled={!!exportLoading}
            >
              {exportLoading === 'orders' ? 'Téléchargement…' : 'Export orders.csv'}
            </button>
          </div>
          <div style={{ display: 'flex', alignItems: 'end' }}>
            <button
              type="button"
              onClick={() => void downloadCsv(`/partner/portal/analytics/menu-tracking.csv?${query}`, `menu-tracking-${days}d.csv`, 'menu')}
              style={btn('ghost')}
              disabled={!!exportLoading}
            >
              {exportLoading === 'menu' ? 'Téléchargement…' : 'Download menu-tracking.csv'}
            </button>
          </div>
        </div>
        {exportError ? <div style={{ color: '#ffb4b4' }}>{exportError}</div> : null}
      </div>

      <div style={{ ...cardStyle(), display: 'grid', gap: 8, marginBottom: 16 }}>
        <h3 style={{ margin: 0 }}>Privacy / Identity</h3>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            type="checkbox"
            checked={barIdentityConsent}
            onChange={(e) => void patchConsent(e.target.checked)}
            disabled={consentBusy}
          />
          Show user identity to staff
        </label>
        <div style={{ opacity: 0.8, fontSize: 13 }}>
          L’identité client ne sera visible au staff que si ce toggle bar est ON et que l’utilisateur a aussi donné son consentement.
        </div>
        {consentMessage ? <div style={{ color: consentMessage.includes('Impossible') ? '#ffb4b4' : '#c7ffd8' }}>{consentMessage}</div> : null}
      </div>

      {loading ? <div>Chargement…</div> : null}
      {error ? <div style={{ color: '#ffb4b4' }}>{error}</div> : null}

      {summary ? (
        <div style={{ display: 'grid', gap: 14 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10 }}>
            <div style={cardStyle()}><b>Orders</b><div>{summary.orders.count}</div></div>
            <div style={cardStyle()}><b>CA</b><div>{euro(summary.orders.total_cents)}</div></div>
            <div style={cardStyle()}><b>Paid/Unpaid</b><div>{summary.orders.paid_count} / {summary.orders.unpaid_count}</div></div>
            <div style={cardStyle()}><b>Tickets payés</b><div>{summary.orders.paid_tickets_total}</div></div>
          </div>

          <div style={cardStyle()}>
            <h3 style={{ marginTop: 0 }}>Top menu items</h3>
            <div style={{ marginBottom: 10, opacity: 0.85 }}>
              Totaux: {summary.menu.totals.views} views • {summary.menu.totals.adds} adds
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th align="left">Item</th>
                  <th align="right">Views</th>
                  <th align="right">Adds</th>
                </tr>
              </thead>
              <tbody>
                {summary.menu.top_items.map((item) => (
                  <tr key={item.item_id ?? item.name}>
                    <td style={{ padding: '6px 0' }}>{item.name}</td>
                    <td align="right">{item.views}</td>
                    <td align="right">{item.adds}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={cardStyle()}>
            <h3 style={{ marginTop: 0 }}>Polymarket</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10 }}>
              <div>LIVE: <b>{summary.polymarket.bets_live}</b></div>
              <div>PENDING: <b>{summary.polymarket.bets_pending}</b></div>
              <div>FINALIZED: <b>{summary.polymarket.bets_finalized}</b></div>
              <div>Stake total: <b>{summary.polymarket.total_staked_tickets}</b></div>
              <div>Payout total: <b>{summary.polymarket.total_payout_tickets}</b></div>
            </div>
          </div>
        </div>
      ) : null}
    </Layout>
  )
}
