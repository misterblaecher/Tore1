import React, { useMemo, useState } from 'react'
import Layout, { inputStyle } from '../ui/Layout'
import { API_BASE, api } from '../lib/api'
import { getSession, getToken } from '../lib/auth'
import { CursorPager, EmptyState, InlineAlert } from '../lib/ui'

type Zone = {
  id: number
  bar_id: number
  event_id?: number | null
  name: string
  slug: string
  enabled: boolean
  qr_payload: string
  created_at: string
}

type Page = { items: Zone[]; next_cursor: string | null }

export default function ZonesAdmin() {
  const session = getSession()
  const barId = session?.bar_id

  const [items, setItems] = useState<Zone[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [newName, setNewName] = useState('')
  const [eventId, setEventId] = useState('')
  const [selected, setSelected] = useState<Record<number, boolean>>({})

  const selectedIds = useMemo(() => Object.keys(selected).filter((id) => selected[Number(id)]).map(Number), [selected])

  const load = async (next?: string | null) => {
    if (!barId) return
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ limit: '50' })
      if (q.trim()) params.set('q', q.trim())
      if (next) params.set('cursor', next)
      const res = await api<Page>(`/bars/${barId}/zones?${params.toString()}`)
      setCursor(res.next_cursor)
      setItems((prev) => (next ? [...prev, ...res.items] : res.items))
    } catch (e: any) {
      setError(e?.message || 'Erreur chargement zones')
    } finally {
      setLoading(false)
    }
  }

  const createZone = async () => {
    if (!barId || !newName.trim()) return
    setLoading(true)
    setError(null)
    try {
      await api<Zone>(`/bars/${barId}/zones`, {
        method: 'POST',
        body: JSON.stringify({ name: newName.trim(), event_id: eventId ? Number(eventId) : null }),
      })
      setNewName('')
      await load()
    } catch (e: any) {
      setError(e?.message || 'Erreur création zone')
    } finally {
      setLoading(false)
    }
  }

  const toggleOne = async (zone: Zone, enabled: boolean) => {
    try {
      const updated = await api<Zone>(`/zones/${zone.id}`, { method: 'PATCH', body: JSON.stringify({ enabled }) })
      setItems((prev) => prev.map((z) => (z.id === zone.id ? updated : z)))
    } catch (e: any) {
      setError(e?.message || 'Erreur update zone')
    }
  }

  const bulk = async (action: 'enable' | 'disable' | 'delete') => {
    if (!barId || selectedIds.length === 0) return
    setLoading(true)
    setError(null)
    try {
      await api(`/bars/${barId}/zones/bulk`, {
        method: 'POST',
        body: JSON.stringify({ zone_ids: selectedIds, action }),
      })
      setSelected({})
      await load()
    } catch (e: any) {
      setError(e?.message || 'Erreur bulk zones')
    } finally {
      setLoading(false)
    }
  }

  const exportPack = async (format: 'zip' | 'pdf') => {
    if (!barId) return
    setLoading(true)
    setError(null)
    try {
      const token = getToken()
      const res = await fetch(`${API_BASE}/bars/${barId}/zones/export_pack?format=${format}`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) throw new Error(`Export failed: ${res.status}`)
      const blob = await res.blob()
      const a = document.createElement('a')
      const url = URL.createObjectURL(blob)
      a.href = url
      a.download = `zones_pack.${format}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      setError(e?.message || 'Erreur export pack')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout title="Zones Admin">
      {!barId ? <InlineAlert tone="error">Session partenaire introuvable.</InlineAlert> : null}

      <div style={{ display: 'grid', gap: 8, gridTemplateColumns: '1fr 180px 120px' }}>
        <input style={inputStyle()} placeholder="Nom de zone (Table 1)" value={newName} onChange={(e) => setNewName(e.target.value)} />
        <input style={inputStyle()} placeholder="event_id (optionnel)" value={eventId} onChange={(e) => setEventId(e.target.value)} />
        <button disabled={loading || !newName.trim() || !barId} onClick={createZone}>Ajouter</button>
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
        <input style={{ ...inputStyle(), minWidth: 260 }} placeholder="Recherche nom/slug" value={q} onChange={(e) => setQ(e.target.value)} />
        <button disabled={loading || !barId} onClick={() => load()}>{loading ? 'Chargement…' : 'Charger zones'}</button>
        <button disabled={loading || selectedIds.length === 0} onClick={() => bulk('enable')}>Bulk ON</button>
        <button disabled={loading || selectedIds.length === 0} onClick={() => bulk('disable')}>Bulk OFF</button>
        <button disabled={loading || selectedIds.length === 0} onClick={() => bulk('delete')}>Bulk DELETE</button>
        <button disabled={loading || !barId} onClick={() => exportPack('zip')}>Export ZIP</button>
        <button disabled={loading || !barId} onClick={() => exportPack('pdf')}>Export PDF</button>
      </div>

      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {!loading && items.length === 0 ? <EmptyState title="Aucune zone" body="Crée d'abord des zones." /> : null}

      <div style={{ marginTop: 10, display: 'grid', gap: 6 }}>
        {items.map((z) => (
          <div key={z.id} style={{ border: '1px solid #2e3440', borderRadius: 10, padding: 10, display: 'grid', gridTemplateColumns: '28px 1fr auto auto', gap: 8, alignItems: 'center' }}>
            <input type="checkbox" checked={!!selected[z.id]} onChange={(e) => setSelected((prev) => ({ ...prev, [z.id]: e.target.checked }))} />
            <div>
              <div style={{ fontWeight: 700 }}>{z.name} <span style={{ opacity: 0.7 }}>({z.slug})</span></div>
              <div style={{ fontSize: 12, opacity: 0.8 }}>{z.qr_payload}</div>
            </div>
            <button onClick={() => toggleOne(z, !z.enabled)}>{z.enabled ? 'ON' : 'OFF'}</button>
            <button onClick={async () => { await navigator.clipboard.writeText(z.qr_payload) }}>Copier QR</button>
          </div>
        ))}
      </div>

      <CursorPager nextCursor={cursor} onNext={() => load(cursor)} />
    </Layout>
  )
}
