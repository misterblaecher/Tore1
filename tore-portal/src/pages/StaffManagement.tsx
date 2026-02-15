import React, { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'
import { Button, Card, InlineAlert } from '../lib/ui'

type StaffRole = 'ENTRY' | 'BAR' | 'MANAGER'

type StaffAssignment = {
  id: number
  eventId: number
  role: StaffRole
  label?: string | null
  createdAt: string
  revokedAt?: string | null
  status: 'ACTIVE' | 'REVOKED' | 'EXPIRED'
  token?: {
    tokenId: string
    type: string
    payload: string
    expiresAt: string
    revokedAt?: string | null
    status: 'ACTIVE' | 'REVOKED' | 'EXPIRED'
  } | null
}

export default function StaffManagement() {
  const { eventId } = useParams()
  const [items, setItems] = useState<StaffAssignment[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [role, setRole] = useState<StaffRole>('ENTRY')
  const [label, setLabel] = useState('')
  const [expiresAt, setExpiresAt] = useState('')
  const [createdQr, setCreatedQr] = useState<string | null>(null)
  const [createdInfo, setCreatedInfo] = useState<{role: string; tokenId: string} | null>(null)

  const refresh = async () => {
    if (!eventId) return
    setLoading(true)
    try {
      const res = await api<{ items: StaffAssignment[] }>(`/partner/portal/orga/events/${eventId}/staff`)
      setItems(res.items || [])
      setError(null)
    } catch (e: any) {
      setError(e?.message ?? 'Erreur chargement staff')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [eventId])

  useEffect(() => {
    if (!eventId) return
    const dt = new Date(Date.now() + 6 * 3600 * 1000)
    setExpiresAt(dt.toISOString().slice(0, 16))
  }, [eventId])

  const activeItems = useMemo(() => items.filter((it) => it.status === 'ACTIVE' && it.token?.payload), [items])

  const create = async () => {
    if (!eventId) return
    setCreating(true)
    try {
      const idem = `staff-create-${eventId}-${Date.now()}`
      const payload = {
        role,
        label: label.trim() || undefined,
        expiresAt: expiresAt ? new Date(expiresAt).toISOString() : undefined,
      }
      const res = await api<any>(`/partner/portal/orga/events/${eventId}/staff`, {
        method: 'POST',
        headers: { 'Idempotency-Key': idem },
        body: JSON.stringify(payload),
      })
      setCreatedQr(res?.qr?.raw ?? null)
      setCreatedInfo({ role, tokenId: res?.qr?.tokenId ?? '' })
      setShowAdd(false)
      setLabel('')
      await refresh()
    } catch (e: any) {
      setError(e?.message ?? 'Erreur création staff')
    } finally {
      setCreating(false)
    }
  }

  const revoke = async (item: StaffAssignment) => {
    const reason = window.prompt(`Raison de révocation pour ${item.role}${item.label ? ` (${item.label})` : ''}`)
    if (!reason || !reason.trim()) return
    try {
      await api(`/partner/portal/orga/staff/${item.id}/revoke`, {
        method: 'POST',
        body: JSON.stringify({ reason: reason.trim() }),
      })
      await refresh()
    } catch (e: any) {
      setError(e?.message ?? 'Erreur révocation')
    }
  }

  return (
    <Layout title="Staff & QR Pack">
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      <Card>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Button onClick={() => setShowAdd(true)}>Add staff</Button>
          <Button variant="secondary" onClick={() => window.print()} disabled={activeItems.length === 0}>Print pack</Button>
          <Link to={`/event-control/${eventId}`} className="btn">Back ORGA HUB</Link>
        </div>
      </Card>

      {showAdd ? (
        <Card>
          <strong>Create staff assignment</strong>
          <div style={{ display: 'grid', gap: 8, marginTop: 8, maxWidth: 420 }}>
            <select value={role} onChange={(e) => setRole(e.target.value as StaffRole)}>
              <option value="ENTRY">ENTRY</option>
              <option value="BAR">BAR</option>
              <option value="MANAGER">MANAGER</option>
            </select>
            <input placeholder="Label optionnel (ex: Entry gate A)" value={label} onChange={(e) => setLabel(e.target.value)} />
            <label>
              Expires at
              <input type="datetime-local" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} />
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <Button onClick={create} disabled={creating}>{creating ? 'Creating…' : 'Create'}</Button>
              <Button variant="secondary" onClick={() => setShowAdd(false)}>Cancel</Button>
            </div>
          </div>
        </Card>
      ) : null}

      {createdQr ? (
        <Card>
          <strong>QR created ({createdInfo?.role})</strong>
          <div style={{ marginTop: 8, fontSize: 12, opacity: 0.8 }}>token: {createdInfo?.tokenId}</div>
          <textarea readOnly value={createdQr} style={{ width: '100%', minHeight: 80, marginTop: 8 }} />
        </Card>
      ) : null}

      <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
        {loading ? <Card>Chargement...</Card> : null}
        {items.map((item) => (
          <Card key={item.id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <div>
                <strong>{item.role}</strong> {item.label ? `— ${item.label}` : ''}
                <div style={{ fontSize: 12, opacity: 0.75 }}>expires: {item.token?.expiresAt ? new Date(item.token.expiresAt).toLocaleString() : 'n/a'}</div>
              </div>
              <span className={`chip chip-${item.status === 'ACTIVE' ? 'ok' : item.status === 'REVOKED' ? 'danger' : 'warn'}`}>{item.status}</span>
            </div>
            {item.token?.payload ? <textarea readOnly value={item.token.payload} style={{ width: '100%', minHeight: 70, marginTop: 8 }} /> : null}
            {item.status === 'ACTIVE' ? <Button variant="secondary" onClick={() => revoke(item)}>Revoke</Button> : null}
          </Card>
        ))}
      </div>
    </Layout>
  )
}
