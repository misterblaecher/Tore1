import React, { useState } from 'react'
import Layout from '../ui/Layout'
import { api } from '../lib/api'

export default function WalletAdmin() {
  const [eventId, setEventId] = useState('')
  const [userId, setUserId] = useState('')
  const [amount, setAmount] = useState('10')
  const [reason, setReason] = useState('manual topup')
  const [logs, setLogs] = useState<any[]>([])

  const topup = async () => {
    await api('/partner/portal/wallet/admin/topup', {
      method: 'POST',
      body: JSON.stringify({
        event_id: Number(eventId),
        user_id: userId,
        amount_tickets: Number(amount),
        reason,
        idempotency_key: `portal-${Date.now()}`,
      }),
    })
    const rows = await api<any[]>(`/partner/portal/wallet/admin/logs?event_id=${Number(eventId)}`)
    setLogs(rows)
  }

  return (
    <Layout title="Wallet Admin">
      <input placeholder="Event ID" value={eventId} onChange={(e) => setEventId(e.target.value)} />
      <input placeholder="User ID" value={userId} onChange={(e) => setUserId(e.target.value)} />
      <input placeholder="Amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
      <input placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)} />
      <button onClick={topup}>Topup</button>
      <pre>{JSON.stringify(logs, null, 2)}</pre>
    </Layout>
  )
}
