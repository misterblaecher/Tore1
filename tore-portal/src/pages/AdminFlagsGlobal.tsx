import { useEffect, useState } from 'react'
import Layout from '../ui/Layout'
import { api } from '../lib/api'

type FlagRow = { key: string; enabled: boolean; reason: string }

export default function AdminFlagsGlobal() {
  const [flags, setFlags] = useState<FlagRow[]>([])

  async function load() {
    const data = await api<{ items: FlagRow[] }>('/admin/flags')
    setFlags(data.items)
  }

  useEffect(() => {
    load().catch(console.error)
  }, [])

  async function save(flag: FlagRow) {
    await api('/admin/flags', {
      method: 'PUT',
      headers: { 'Idempotency-Key': `flag-${flag.key}-${Date.now()}` },
      body: JSON.stringify(flag),
    })
    await load()
  }

  return (
    <Layout title="Admin Flags Global">
      <button onClick={load}>Refresh</button>
      <ul>
        {flags.map((f) => (
          <li key={f.key}>
            <strong>{f.key}</strong>
            <label style={{ marginLeft: 8 }}>
              <input type="checkbox" checked={f.enabled} onChange={(e) => setFlags((prev) => prev.map((row) => (row.key === f.key ? { ...row, enabled: e.target.checked } : row)))} /> enabled
            </label>
            <input value={f.reason || ''} onChange={(e) => setFlags((prev) => prev.map((row) => (row.key === f.key ? { ...row, reason: e.target.value } : row)))} placeholder="reason" style={{ marginLeft: 8 }} />
            <button onClick={() => save(f)} style={{ marginLeft: 8 }}>Save</button>
          </li>
        ))}
      </ul>
    </Layout>
  )
}
