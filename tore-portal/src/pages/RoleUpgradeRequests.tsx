import { useState } from 'react'
import Layout from '../ui/Layout'
import { adminApi } from '../lib/api'

type RoleRequest = {
  id: number
  user_id: string
  requested_mode: 'organizer' | 'team'
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  note?: string | null
}

export default function RoleUpgradeRequests() {
  const [rows, setRows] = useState<RoleRequest[]>([])
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true)
    const data = await adminApi<{ items: RoleRequest[] }>('/admin/role-requests?status=pending&limit=100')
    setRows(data.items)
    setLoading(false)
  }

  async function review(id: number, action: 'approve' | 'reject') {
    await adminApi(`/admin/role-requests/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ action }),
    })
    setRows((prev) => prev.filter((r) => r.id !== id))
  }

  return (
    <Layout title="Admin • Demandes de rôle">
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button onClick={load} disabled={loading}>{loading ? 'Chargement...' : 'Recharger'}</button>
      </div>
      <table style={{ width: '100%' }}>
        <thead><tr><th>ID</th><th>User</th><th>Mode</th><th>Créée le</th><th>Actions</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.id}</td>
              <td>{row.user_id}</td>
              <td>{row.requested_mode}</td>
              <td>{new Date(row.created_at).toLocaleString()}</td>
              <td>
                <button onClick={() => review(row.id, 'approve')}>Approve</button>
                <button onClick={() => review(row.id, 'reject')} style={{ marginLeft: 8 }}>Reject</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Layout>
  )
}
