import { useMemo, useState } from 'react'
import Layout from '../ui/Layout'

type Parsed = { type: string; payload: string }

function parseQr(raw: string): Parsed {
  const value = raw.trim()
  if (!value) return { type: 'unknown', payload: '' }

  const lower = value.toLowerCase()
  if (lower.startsWith('event_checkin:')) return { type: 'event_checkin', payload: value.slice('event_checkin:'.length) }
  if (lower.startsWith('bar:')) return { type: 'bar', payload: value.slice('bar:'.length) }
  if (lower.startsWith('profile:')) return { type: 'profile', payload: value.slice('profile:'.length) }

  return { type: 'unknown', payload: value }
}

export default function QrDebug() {
  const [raw, setRaw] = useState('')
  const parsed = useMemo(() => parseQr(raw), [raw])

  return (
    <Layout title="QR Debug">
      <textarea value={raw} onChange={(e) => setRaw(e.target.value)} placeholder="Scanne/colle un QR" style={{ width: '100%', minHeight: 120 }} />
      <p><strong>Type:</strong> {parsed.type}</p>
      <p><strong>Payload:</strong> <code>{parsed.payload || '-'}</code></p>
      {parsed.type === 'unknown' ? <p style={{ color: '#b45309' }}>QR non reconnu.</p> : null}
    </Layout>
  )
}
