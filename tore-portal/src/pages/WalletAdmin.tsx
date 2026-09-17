import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Layout, { inputStyle } from '../ui/Layout'
import { api, apiText } from '../lib/api'
import { createRetryableWrite } from '../lib/retryable-write'
import { CursorPager, EmptyState, InlineAlert } from '../lib/ui'

type WalletPage = { items: any[]; next_cursor: string | null }
type ScanResolve = { userId: string | null; raw: string; reason?: string }

type TopupResult = {
  kind: 'success' | 'duplicate' | 'denied'
  message: string
}

type Snapshot = {
  event_state?: string
  modules?: Record<string, { effective_state?: 'ON' | 'OFF' | 'READ_ONLY'; reason?: string | null }>
}

const reasonToLabel: Record<string, string> = {
  event_paused: 'event_paused',
  module_off: 'module_off',
  rate_limited: 'rate_limited',
  invalid_amount: 'invalid_amount',
  insufficient_balance: 'insufficient_balance',
}

const parseTopupTarget = (rawInput: string): ScanResolve => {
  const raw = rawInput.trim()
  if (!raw) return { userId: null, raw, reason: 'empty' }

  if (raw.startsWith('tore://')) {
    try {
      const normalized = raw.replace('tore://', 'https://tore.local/')
      const url = new URL(normalized)
      if (url.pathname.replace(/^\//, '') !== 'user') {
        return { userId: null, raw, reason: 'unsupported_qr' }
      }
      const userId = url.searchParams.get('uid') || url.searchParams.get('user_id')
      return { userId, raw, reason: userId ? undefined : 'missing_uid' }
    } catch {
      return { userId: null, raw, reason: 'invalid_qr' }
    }
  }

  return { userId: raw, raw }
}

export default function WalletAdmin() {
  const [params, setParams] = useSearchParams()
  const [userId, setUserId] = useState('')
  const [amount, setAmount] = useState('10')
  const [reason, setReason] = useState('manual topup')
  const [logs, setLogs] = useState<any[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filterType, setFilterType] = useState('')
  const [filterQ, setFilterQ] = useState('')
  const [loading, setLoading] = useState(false)
  const [scanInput, setScanInput] = useState('')
  const [scanAmount, setScanAmount] = useState('10')
  const [scanResult, setScanResult] = useState<TopupResult | null>(null)
  const busy = useRef(false)
  const [submitting, setSubmitting] = useState(false)
  const topupWrite = useRef(createRetryableWrite((body, key) =>
    api<{ idempotent?: boolean }>('/partner/portal/wallet/topup', {
      method: 'POST', headers: { 'Idempotency-Key': key }, body,
    })))
  const submitTopup = topupWrite.current

  const eventId = params.get('event_id') || ''
  const filterUserId = params.get('user_id') || ''

  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const moduleState = snapshot?.modules?.wallet_enabled?.effective_state || 'ON'
  const eventState = (snapshot?.event_state || 'LIVE').toUpperCase()
  const writesDisabledReason = useMemo(() => {
    if (!Number.isSafeInteger(Number(eventId)) || Number(eventId) <= 0) return 'Sélectionner un événement'
    if (!snapshot) return 'État de l’événement indisponible : recharge suspendue'
    if (moduleState === 'OFF') return 'Module désactivé'
    if (moduleState === 'READ_ONLY') return `Événement ${eventState}: write désactivé (read-only)`
    return null
  }, [eventState, moduleState, eventId, snapshot])

  useEffect(() => {
    setSnapshot(null)
    setLogs([])
    setCursor(null)
    setError(null)
    setScanResult(null)
    if (!eventId) return
    let active = true
    api<Snapshot>(`/partner/portal/event/${Number(eventId)}/state-snapshot`)
      .then((value) => { if (active) setSnapshot(value) })
      .catch(() => { if (active) setSnapshot(null) })
    return () => { active = false }
  }, [eventId])

  const loadLogs = async (next?: string | null) => {
    setLoading(true)
    setError(null)
    try {
      const q = new URLSearchParams({ event_id: String(Number(eventId)), limit: '50' })
      if (filterUserId.trim()) q.set('user_id', filterUserId.trim())
      if (filterType.trim()) q.set('type', filterType.trim())
      if (filterQ.trim()) q.set('q', filterQ.trim())
      if (next) q.set('cursor', next)
      const rows = await api<WalletPage>(`/partner/portal/wallet/logs?${q.toString()}`)
      setCursor(rows.next_cursor)
      setLogs((prev) => (next ? [...prev, ...rows.items] : rows.items))
    } catch (e: any) {
      setError(e?.message || 'Erreur chargement wallet logs')
    } finally {
      setLoading(false)
    }
  }

  const topup = async () => {
    if (busy.current) return
    if (writesDisabledReason) {
      setError(writesDisabledReason)
      return
    }
    if (!userId.trim() || !Number.isSafeInteger(Number(amount)) || Number(amount) <= 0) {
      setError('Utilisateur et montant entier positif requis')
      return
    }
    busy.current = true
    setSubmitting(true)
    setError(null)
    try {
      await submitTopup({ event_id: Number(eventId), target_user_id: userId.trim(), amount_cents: Number(amount), reason_code: 'manual_topup', reason_text: reason })
      await loadLogs()
    } catch (e: any) {
      const reason = e?.reason
      setError(reasonToLabel[reason] || e?.message || 'Topup refusé')
    } finally {
      busy.current = false
      setSubmitting(false)
    }
  }

  const topupByScan = async () => {
    if (busy.current) return
    if (writesDisabledReason) {
      setScanResult({ kind: 'denied', message: writesDisabledReason })
      return
    }
    setScanResult(null)
    const parsed = parseTopupTarget(scanInput)
    if (!parsed.userId) {
      setScanResult({ kind: 'denied', message: `denied: ${parsed.reason || 'invalid_target'}` })
      return
    }
    if (!Number.isSafeInteger(Number(scanAmount)) || Number(scanAmount) <= 0) {
      setScanResult({ kind: 'denied', message: 'Montant entier positif requis' })
      return
    }
    busy.current = true
    setSubmitting(true)
    try {
      const payload = await submitTopup({
          event_id: Number(eventId),
          target_user_id: parsed.userId,
          amount_cents: Number(scanAmount),
          reason_code: 'scan_topup',
          reason_text: `scan:${parsed.raw}`,
      })
      setScanResult({ kind: payload?.idempotent ? 'duplicate' : 'success', message: payload?.idempotent ? 'duplicate' : 'success' })
      await loadLogs()
    } catch (e: any) {
      const status = Number(e?.status || 0)
      const reason = e?.reason || e?.detail?.reason || 'unknown'
      if (status === 429) {
        setScanResult({ kind: 'denied', message: `denied: cooldown (${reason})` })
      } else {
        setScanResult({ kind: 'denied', message: `denied: ${reason}` })
      }
    } finally {
      busy.current = false
      setSubmitting(false)
    }
  }

  const exportCsv = async () => {
    try {
      const csv = await apiText(`/partner/portal/wallet/logs/export.csv?event_id=${Number(eventId)}`)
      const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
      const link = document.createElement('a')
      link.href = url
      link.download = `wallet-${eventId}.csv`
      link.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Export indisponible')
    }
  }

  return (
    <Layout title="Wallet Admin">
      <InlineAlert tone="warning">Event state: {eventState}</InlineAlert>
      {writesDisabledReason ? <InlineAlert tone="warning">{writesDisabledReason}</InlineAlert> : null}
      <input style={inputStyle()} placeholder="Event ID" value={eventId} onChange={(e) => setParams({ event_id: e.target.value, user_id: filterUserId })} />
      <input style={{ ...inputStyle(), marginTop: 8 }} placeholder="User ID" value={userId} onChange={(e) => setUserId(e.target.value)} />
      <input style={{ ...inputStyle(), marginTop: 8 }} placeholder="Amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
      <input style={{ ...inputStyle(), marginTop: 8 }} placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)} />
      <button onClick={topup} style={{ marginTop: 8 }} disabled={submitting || !!writesDisabledReason}>Ajouter des Credits</button>
      <hr />
      <h3>Topup by scan</h3>
      <input
        style={inputStyle()}
        placeholder="Coller tore://user?uid=... ou user_id"
        value={scanInput}
        onChange={(e) => setScanInput(e.target.value)}
      />
      <input
        style={{ ...inputStyle(), marginTop: 8 }}
        placeholder="Amount tickets"
        value={scanAmount}
        onChange={(e) => setScanAmount(e.target.value)}
      />
      <button onClick={topupByScan} style={{ marginTop: 8 }} disabled={submitting || !!writesDisabledReason}>Recharger après scan</button>
      {scanResult ? <InlineAlert tone={scanResult.kind === 'denied' ? 'error' : 'success'}>{scanResult.message}</InlineAlert> : null}
      <hr />
      <input style={inputStyle()} placeholder="Filter user_id" value={filterUserId} onChange={(e) => setParams({ event_id: eventId, user_id: e.target.value })} />
      <input style={{ ...inputStyle(), marginTop: 8 }} placeholder="Filter type" value={filterType} onChange={(e) => setFilterType(e.target.value)} />
      <input style={{ ...inputStyle(), marginTop: 8 }} placeholder="Search q" value={filterQ} onChange={(e) => setFilterQ(e.target.value)} />
      <button onClick={() => loadLogs()} style={{ marginTop: 8 }} disabled={loading}>{loading ? 'Chargement…' : 'Load logs'}</button>
      <button onClick={exportCsv} style={{ marginTop: 8, marginLeft: 8 }}>Export CSV</button>
      <CursorPager nextCursor={cursor} onNext={() => loadLogs(cursor)} />
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {!loading && logs.length === 0 ? <EmptyState title="Aucun log wallet" /> : null}
      <pre>{JSON.stringify(logs, null, 2)}</pre>
    </Layout>
  )
}
