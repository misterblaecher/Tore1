import React, { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Layout, { inputStyle } from '../ui/Layout'
import { api } from '../lib/api'
import { CursorPager, EmptyState, InlineAlert } from '../lib/ui'

type WalletPage = { items: any[]; next_cursor: string | null }

const reasonToLabel: Record<string, string> = {
  event_paused: 'event_paused',
  module_off: 'module_off',
  rate_limited: 'rate_limited',
  invalid_amount: 'invalid_amount',
  insufficient_balance: 'insufficient_balance',
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

  const eventId = params.get('event_id') || ''
  const filterUserId = params.get('user_id') || ''

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
    setError(null)
    try {
      await api('/partner/portal/wallet/topup', {
        method: 'POST',
        headers: { 'Idempotency-Key': `portal-${Date.now()}` },
        body: JSON.stringify({ event_id: Number(eventId), target_user_id: userId, amount_cents: Number(amount), note: reason, client_key: `portal-${Date.now()}` }),
      })
      await loadLogs()
    } catch (e: any) {
      const reason = e?.reason
      setError(reasonToLabel[reason] || e?.message || 'Topup refusé')
    }
  }

  const exportCsv = async () => {
    window.open(`/partner/portal/wallet/logs/export.csv?event_id=${Number(eventId)}`, '_blank', 'noopener,noreferrer')
  }

  return (
    <Layout title="Wallet Admin">
      <input style={inputStyle()} placeholder="Event ID" value={eventId} onChange={(e) => setParams({ event_id: e.target.value, user_id: filterUserId })} />
      <input style={{ ...inputStyle(), marginTop: 8 }} placeholder="User ID" value={userId} onChange={(e) => setUserId(e.target.value)} />
      <input style={{ ...inputStyle(), marginTop: 8 }} placeholder="Amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
      <input style={{ ...inputStyle(), marginTop: 8 }} placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)} />
      <button onClick={topup} style={{ marginTop: 8 }}>Topup</button>
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
