import { useState } from 'react'
import Layout from '../ui/Layout'
import { api } from '../lib/api'

type UserRow = { id: string; displayName: string }
type SanctionRow = { id: number; type: string; status: string; reason: string }

export default function AdminUsersGlobal() {
  const [query, setQuery] = useState('')
  const [users, setUsers] = useState<UserRow[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [sanctions, setSanctions] = useState<SanctionRow[]>([])

  async function search() {
    const data = await api<{ items: UserRow[] }>(`/admin/users?query=${encodeURIComponent(query)}`)
    setUsers(data.items)
  }

  async function loadSanctions(userId: string) {
    setSelected(userId)
    const data = await api<{ items: SanctionRow[] }>(`/admin/users/${userId}/sanctions`)
    setSanctions(data.items)
  }

  async function createSanction() {
    if (!selected) return
    await api(`/admin/users/${selected}/sanctions`, {
      method: 'POST',
      headers: { 'Idempotency-Key': `sanction-${Date.now()}` },
      body: JSON.stringify({ type: 'WARN', reason: 'manual warning' }),
    })
    await loadSanctions(selected)
  }

  async function revoke(id: number) {
    if (!selected) return
    await api(`/admin/users/${selected}/sanctions/${id}/revoke`, {
      method: 'POST',
      headers: { 'Idempotency-Key': `revoke-${Date.now()}` },
      body: JSON.stringify({ reason: 'manual revoke' }),
    })
    await loadSanctions(selected)
  }

  return (
    <Layout title="Admin Users Global">
      <div style={{ display: 'flex', gap: 8 }}>
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Recherche user" />
        <button onClick={search}>Rechercher</button>
      </div>
      <div style={{ marginTop: 12 }}>
        {users.map((u) => (
          <button key={u.id} onClick={() => loadSanctions(u.id)} style={{ display: 'block', marginBottom: 6 }}>
            {u.displayName} ({u.id})
          </button>
        ))}
      </div>
      {selected ? <button onClick={createSanction}>Créer WARN</button> : null}
      <ul>
        {sanctions.map((s) => (
          <li key={s.id}>
            #{s.id} {s.type} / {s.status} - {s.reason} {s.status === 'ACTIVE' ? <button onClick={() => revoke(s.id)}>Revoke</button> : null}
          </li>
        ))}
      </ul>
    </Layout>
  )
}
