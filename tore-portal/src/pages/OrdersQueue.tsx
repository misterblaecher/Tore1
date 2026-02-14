import React, { useCallback, useEffect, useMemo, useState } from 'react'
import Layout, { cardStyle } from '../ui/Layout'
import { ApiError, api } from '../lib/api'
import { CursorPager, EmptyState, InlineAlert } from '../lib/ui'

type OrderItem = { id: number; name_snapshot: string; qty: number; line_total_cents: number }
type OrderRow = { id: number; event_id?: number | null; user_id?: string | null; status: string; payment_status: 'PAID' | 'UNPAID'; note?: string | null; created_at: string; items: OrderItem[]; total_cents?: number }
type LiveResponse = { items: OrderRow[]; next_cursor?: string | null }
type ScanResponse = { idempotent: boolean; order: OrderRow; user_visible_to_staff: boolean; identity_visible?: boolean }

const STATUS_TABS = [
  { key: '', label: 'Tous' },
  { key: 'pending', label: 'Pending' },
  { key: 'accepted', label: 'Accepted' },
  { key: 'ready', label: 'Ready' },
]

const BLOCKED_REASONS = new Set(['event_paused', 'module_off', 'revoked', 'rate_limited'])

const reasonLabel = (reason: string) => {
  const map: Record<string, string> = {
    event_paused: 'Event en pause: actions temporairement bloquées.',
    module_off: 'Module désactivé pour cet event.',
    rate_limited: 'Trop de scans/actions, attends quelques secondes.',
    revoked: 'Action révoquée côté backend.',
    invalid_qr: 'QR invalide.',
    forbidden: 'Action non autorisée.',
  }
  return map[reason] || reason
}

function extractOt(input: string): string {
  const value = input.trim()
  if (!value) return ''
  if (value.startsWith('tore://')) {
    try {
      const url = new URL(value.replace('tore://', 'https://tore.local/'))
      return url.searchParams.get('ot') || ''
    } catch {
      return ''
    }
  }
  return value
}

export default function OrdersQueue() {
  const [orders, setOrders] = useState<OrderRow[]>([])
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [eventFilter, setEventFilter] = useState<string>('')
  const [cursor, setCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string>('')
  const [reason, setReason] = useState<string>('')

  const [scanValue, setScanValue] = useState('')
  const [scanBusy, setScanBusy] = useState(false)
  const [scanError, setScanError] = useState('')
  const [scanReason, setScanReason] = useState('')
  const [scanResult, setScanResult] = useState<ScanResponse | null>(null)
  const [scanCooldownUntil, setScanCooldownUntil] = useState<number>(0)

  const load = useCallback(async (append = false) => {
    if (!eventFilter) {
      setOrders([])
      setCursor(null)
      return
    }
    setLoading(true)
    setError('')
    setReason('')
    try {
      const params = new URLSearchParams({ event_id: eventFilter, limit: '50' })
      if (statusFilter) params.set('status', statusFilter)
      if (append && cursor) params.set('cursor', cursor)
      const res = await api<LiveResponse>(`/orders/live?${params.toString()}`)
      setOrders((prev) => (append ? [...prev, ...res.items] : res.items))
      setCursor(res.next_cursor ?? null)
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.status === 429 ? 'Trop de requêtes, réessaie.' : e.message)
        setReason(e.reason ?? '')
      } else setError('Erreur inattendue')
    } finally {
      setLoading(false)
    }
  }, [cursor, eventFilter, statusFilter])

  useEffect(() => {
    void load(false)
  }, [load])

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return
      if (!eventFilter) return
      void load(false)
    }, 2500)
    return () => window.clearInterval(timer)
  }, [eventFilter, load])

  const updateStatus = async (id: number, status: string) => {
    try {
      await api(`/orders/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) })
      await load(false)
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.status === 429 ? 'Trop de requêtes, réessaie.' : e.message)
        setReason(e.reason ?? '')
      }
    }
  }

  const onScan = async () => {
    if (Date.now() < scanCooldownUntil) return
    const ot = extractOt(scanValue)
    if (!ot) {
      setScanError('Token QR invalide. Colle un lien tore://order?ot=... ou un token ot brut.')
      return
    }
    setScanBusy(true)
    setScanError('')
    setScanReason('')
    try {
      const payload = {
        ot,
        idempotency_key: `scan-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      }
      const res = await api<ScanResponse>('/partner/portal/orders/scan-client-qr', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setScanResult(res)
      if (res.idempotent) {
        setScanError('QR déjà scanné récemment (idempotent).')
      }
      if (eventFilter) await load(false)
    } catch (e) {
      if (e instanceof ApiError) {
        setScanReason(e.reason ?? '')
        if (e.status === 429 || e.reason === 'rate_limited') {
          setScanCooldownUntil(Date.now() + 8000)
        }
        if (e.message.toLowerCase().includes('expired')) {
          setScanError('QR expiré. Demande au client de regénérer son QR.')
        } else if (e.message.toLowerCase().includes('invalid')) {
          setScanError('QR invalide. Re-scan nécessaire.')
        } else {
          setScanError(e.message)
        }
      } else {
        setScanError('Erreur scan QR')
      }
    } finally {
      setScanBusy(false)
    }
  }

  const scanCooldownLeft = Math.max(0, Math.ceil((scanCooldownUntil - Date.now()) / 1000))
  const readOnly = BLOCKED_REASONS.has(reason) || BLOCKED_REASONS.has(scanReason)

  const actions = (status: string, id: number) => {
    if (readOnly) return null
    if (status === 'NEW') return <button onClick={() => void updateStatus(id, 'accepted')}>Accept</button>
    if (status === 'IN_PROGRESS') return <button onClick={() => void updateStatus(id, 'ready')}>Ready</button>
    if (status === 'READY') return <button onClick={() => void updateStatus(id, 'completed')}>Complete</button>
    return null
  }

  const scanIdentityVisible = useMemo(() => {
    if (!scanResult) return false
    return scanResult.identity_visible ?? scanResult.user_visible_to_staff
  }, [scanResult])

  return (
    <Layout title="Orders Live">
      <section style={{ ...cardStyle(), marginBottom: 12 }}>
        <h3 style={{ marginTop: 0 }}>Scan Order Client QR (Mode C)</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input
            style={{ minWidth: 360 }}
            placeholder="tore://order?ot=... ou token ot"
            value={scanValue}
            onChange={(e) => setScanValue(e.target.value)}
          />
          <button onClick={() => void onScan()} disabled={scanBusy || readOnly || scanCooldownLeft > 0}>{scanCooldownLeft > 0 ? `Scan (${scanCooldownLeft}s)` : 'Scan'}</button>
        </div>
        {scanReason ? <InlineAlert tone="warning">{reasonLabel(scanReason)}</InlineAlert> : null}
        {scanCooldownLeft > 0 ? <InlineAlert tone="warning">Trop de requêtes, réessaie dans {scanCooldownLeft}s.</InlineAlert> : null}
        {scanError ? <InlineAlert tone={scanResult?.idempotent ? 'warning' : 'error'}>{scanError}</InlineAlert> : null}
        {scanResult ? (
          <div style={{ marginTop: 8, display: 'grid', gap: 4 }}>
            <div>
              Résultat: <b>{scanResult.idempotent ? 'Déjà scanné' : 'Scan validé'}</b>
            </div>
            <div>
              Order #{scanResult.order.id} — status backend: <b>{scanResult.order.status}</b>
            </div>
            <div>
              Total: {((scanResult.order.total_cents || 0) / 100).toFixed(2)}€ • Items: {scanResult.order.items.map((i) => `${i.qty}x ${i.name_snapshot}`).join(', ')}
            </div>
            {scanIdentityVisible ? <div>Identité client: {scanResult.order.user_id || 'N/A'}</div> : <div>Identité client masquée (consentement requis).</div>}
          </div>
        ) : null}
      </section>

      <div style={{ ...cardStyle(), marginBottom: 12, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <input placeholder="event_id" value={eventFilter} onChange={(e) => setEventFilter(e.target.value)} />
        {STATUS_TABS.map((tab) => (
          <button key={tab.key} onClick={() => setStatusFilter(tab.key)} style={{ fontWeight: statusFilter === tab.key ? 700 : 500 }}>{tab.label}</button>
        ))}
        <button onClick={() => void load(false)} disabled={loading || !eventFilter}>Refresh</button>
      </div>

      {readOnly ? <InlineAlert tone="warning">Actions désactivées ({reason || scanReason}).</InlineAlert> : null}
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {!eventFilter ? <EmptyState title="Saisis un event_id" body="Le live orders nécessite un event_id." /> : null}
      {eventFilter && !loading && orders.length === 0 ? <EmptyState title="Aucune commande" /> : null}

      {orders.map((o) => (
        <section key={o.id} style={{ ...cardStyle(), marginBottom: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <strong>#{o.id}</strong> — {o.status}
              {o.note ? <div style={{ opacity: 0.75 }}>{o.note}</div> : null}
            </div>
            {actions(o.status, o.id)}
          </div>
          <div style={{ marginTop: 8 }}>
            {o.items.map((it) => (
              <div key={it.id}>{it.qty}x {it.name_snapshot} — {(it.line_total_cents / 100).toFixed(2)}€</div>
            ))}
          </div>
        </section>
      ))}

      <CursorPager nextCursor={cursor} onNext={() => void load(true)} />
    </Layout>
  )
}
