import { useEffect, useState } from 'react'
import Layout from '../ui/Layout'
import { api } from '../lib/api'

type AuditRow = {
  id: number
  ts: string
  actorUserId?: string | null
  action: string
  entityType: string
  entityId?: string | null
  idempotencyKey?: string | null
}

export default function AdminAuditGlobal() {
  const [items, setItems] = useState<AuditRow[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [q, setQ] = useState('')

  const load = async (next?: string | null) => {
    const params = new URLSearchParams()
    if (q) params.set('user', q)
    if (next) params.set('cursor', next)
    const data = await api<{ items: AuditRow[]; nextCursor?: string | null }>(`/admin/audit?${params.toString()}`)
    setItems(data.items)
    setCursor(data.nextCursor || null)
  }

  useEffect(() => {
    load().catch(console.error)
  }, [])

  return (
    <Layout title="Admin Audit Global">
      <div style={{ display: 'flex', gap: 8 }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filtre user/actor" />
        <button onClick={() => load()}>Rechercher</button>
      </div>
      <table style={{ width: '100%', marginTop: 12 }}>
        <thead><tr><th>ID</th><th>TS</th><th>Actor</th><th>Action</th><th>Entity</th><th>Idempotency</th></tr></thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.id}>
              <td>{row.id}</td><td>{row.ts}</td><td>{row.actorUserId || '-'}</td><td>{row.action}</td><td>{row.entityType}:{row.entityId || '-'}</td><td>{row.idempotencyKey || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {cursor ? <button onClick={() => load(cursor)}>Page suivante</button> : null}
    </Layout>
  )
}
