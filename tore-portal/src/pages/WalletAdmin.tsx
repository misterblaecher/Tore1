import React, { useState } from 'react'
import Layout, { inputStyle } from '../ui/Layout'
import { api } from '../lib/api'

type WalletPage = { items: any[]; next_cursor: string | null }

export default function WalletAdmin() {
  const [eventId, setEventId] = useState('')
  const [userId, setUserId] = useState('')
  const [amount, setAmount] = useState('10')
  const [reason, setReason] = useState('manual topup')
  const [filterUserId, setFilterUserId] = useState('')
  const [logs, setLogs] = useState<any[]>([])
  const [cursor, setCursor] = useState<string | null>(null)

  const loadLogs = async (next?: string | null) => {
    const params = new URLSearchParams({ event_id: String(Number(eventId)), limit: '50' })
    if (filterUserId.trim()) params.set('user_id', filterUserId.trim())
    if (next) params.set('cursor', next)
    const rows = await api<WalletPage>(`/partner/portal/wallet/admin/logs?${params.toString()}`)
    setCursor(rows.next_cursor)
    setLogs((prev) => (next ? [...prev, ...rows.items] : rows.items))
  }

  const topup = async () => {
    await api('/partner/portal/wallet/admin/topup', {
      method: 'POST',
      body: JSON.stringify({ event_id: Number(eventId), user_id: userId, amount_tickets: Number(amount), reason, idempotency_key: `portal-${Date.now()}` }),
    })
    await loadLogs()
  }

  return (
    <Layout title="Wallet Admin">
      <input style={inputStyle()} placeholder="Event ID" value={eventId} onChange={(e) => setEventId(e.target.value)} />
      <input style={{ ...inputStyle(), marginTop: 8 }} placeholder="User ID" value={userId} onChange={(e) => setUserId(e.target.value)} />
      <input style={{ ...inputStyle(), marginTop: 8 }} placeholder="Amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
      <input style={{ ...inputStyle(), marginTop: 8 }} placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)} />
      <button onClick={topup} style={{ marginTop: 8 }}>Topup</button>
      <hr />
      <input style={inputStyle()} placeholder="Filter user_id" value={filterUserId} onChange={(e) => setFilterUserId(e.target.value)} />
      <button onClick={() => loadLogs()} style={{ marginTop: 8 }}>Load logs</button>
      {cursor ? <button onClick={() => loadLogs(cursor)} style={{ marginLeft: 8 }}>Load more</button> : null}
      <pre>{JSON.stringify(logs, null, 2)}</pre>
    </Layout>
  )
}
