import { useEffect, useMemo, useState } from 'react'
import { API_BASE } from '../lib/api'

type HealthPayload = Record<string, unknown>

function isDevEnv() {
  const value = String((import.meta as any).env?.VITE_ENV ?? '').toUpperCase()
  return value === 'DEV' || Boolean(import.meta.env.DEV)
}

export default function DevStatus() {
  const [loading, setLoading] = useState(true)
  const [allowed, setAllowed] = useState(isDevEnv())
  const [error, setError] = useState<string | null>(null)
  const [payload, setPayload] = useState<HealthPayload | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(`${API_BASE}/debug/health-ui`)
        if (cancelled) return
        if (res.status === 200) {
          const body = (await res.json()) as HealthPayload
          setPayload(body)
          setAllowed(true)
        } else if (!isDevEnv()) {
          setAllowed(false)
        }
      } catch (e) {
        if (!cancelled && !isDevEnv()) {
          setAllowed(false)
          setError('Backend /debug/health-ui unreachable.')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const asText = useMemo(() => JSON.stringify(payload ?? {}, null, 2), [payload])

  if (loading) return <div style={{ padding: 24 }}>Loading system status…</div>
  if (!allowed) return <div style={{ padding: 24 }}><h2>404</h2><p>Not found.</p>{error ? <small>{error}</small> : null}</div>

  return (
    <div style={{ maxWidth: 980, margin: '0 auto', padding: 24 }}>
      <h1>DEV System Status</h1>
      <p>Source: <code>{API_BASE}/debug/health-ui</code></p>
      <button
        type="button"
        onClick={async () => {
          await navigator.clipboard.writeText(asText)
        }}
      >
        Copy report
      </button>
      <pre style={{ marginTop: 16, background: '#111', color: '#f5f5f5', padding: 12, borderRadius: 8, overflowX: 'auto' }}>
        {asText}
      </pre>
    </div>
  )
}
