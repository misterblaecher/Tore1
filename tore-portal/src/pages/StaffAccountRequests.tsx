import { useMemo, useState } from 'react'
import Layout from '../ui/Layout'
import { adminApi } from '../lib/api'

type Row = {
  id: number
  created_at: string
  name: string
  email: string
  phone: string
  is_whatsapp: boolean
  source?: string | null
  status: 'pending' | 'processed'
}

export default function StaffAccountRequests() {
  const [status, setStatus] = useState<'pending' | 'processed'>('pending')
  const [rows, setRows] = useState<Row[]>([])
  const [cursor, setCursor] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canExport = useMemo(() => rows.length > 0, [rows])

  async function load(next = false) {
    setLoading(true)
    setError(null)
    try {
      const q = new URLSearchParams({ status, limit: '100' })
      if (next && cursor) q.set('cursor', String(cursor))
      const data = await adminApi<{ items: Row[]; next_cursor?: number | null }>(`/admin/account-requests?${q.toString()}`)
      setRows(next ? [...rows, ...data.items] : data.items)
      setCursor(data.next_cursor ?? null)
    } catch (e: any) {
      setError(e?.message ?? 'Erreur chargement')
    } finally {
      setLoading(false)
    }
  }

  async function markProcessed(id: number) {
    await adminApi(`/admin/account-requests/${id}`, { method: 'PATCH', body: JSON.stringify({ status: 'processed' }) })
    setRows((prev) => prev.map((row) => (row.id === id ? { ...row, status: 'processed' } : row)))
  }

  function exportCsv() {
    const header = ['date', 'name', 'email', 'phone', 'is_whatsapp', 'source', 'status']
    const body = rows.map((row) => [
      new Date(row.created_at).toISOString(),
      row.name,
      row.email,
      row.phone,
      row.is_whatsapp ? 'true' : 'false',
      row.source ?? '',
      row.status,
    ])
    const csv = [header, ...body]
      .map((line) => line.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(','))
      .join('\n')

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `account-requests-${status}.csv`
    link.click()
  }

  return (
    <Layout title="Staff • Account Requests">
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <select value={status} onChange={(e) => setStatus(e.target.value as 'pending' | 'processed')}>
          <option value="pending">pending</option>
          <option value="processed">processed</option>
        </select>
        <button onClick={() => load(false)} disabled={loading}>Reload</button>
        <button onClick={exportCsv} disabled={!canExport}>Export CSV</button>
      </div>

      {error ? <p style={{ color: 'crimson' }}>{error}</p> : null}

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th>Date</th><th>Name</th><th>Email</th><th>Phone</th><th>WA</th><th>Source</th><th>Status</th><th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{new Date(row.created_at).toLocaleString()}</td>
              <td>{row.name}</td>
              <td>{row.email}</td>
              <td>{row.phone}</td>
              <td>{row.is_whatsapp ? 'yes' : 'no'}</td>
              <td>{row.source ?? '-'}</td>
              <td>{row.status}</td>
              <td>{row.status !== 'processed' ? <button onClick={() => markProcessed(row.id)}>Mark processed</button> : null}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {cursor ? <button style={{ marginTop: 12 }} onClick={() => load(true)} disabled={loading}>Load more</button> : null}
    </Layout>
  )
}
