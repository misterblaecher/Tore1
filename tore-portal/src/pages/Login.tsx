import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSession, setSession, setToken } from '../lib/auth'
import { API_BASE } from '../lib/api'
import { isApiUnavailable } from '../lib/errors'
import ApiUnavailable from '../ui/ApiUnavailable'

type AuthOut = {
  token: string
  bar_id: number
  role: string
  display_name: string
}

export default function Login() {
  const nav = useNavigate()
  const session = getSession()
  const [barId, setBarId] = useState<string>(session?.bar_id ? String(session.bar_id) : '')
  const [name, setName] = useState<string>(session?.display_name ?? '')
  const [pin, setPin] = useState<string>(session?.pin ?? '')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [apiDown, setApiDown] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setApiDown(false)
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/partner/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bar_id: Number(barId),
          display_name: name,
          pin,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail ?? `HTTP ${res.status}`)
      }
      const data = (await res.json()) as AuthOut
      setToken(data.token)
      setSession({ bar_id: data.bar_id, display_name: data.display_name, pin, role: data.role })
      nav('/')
    } catch (err: any) {
      if (isApiUnavailable(err)) {
        setApiDown(true)
      } else {
        setError('Impossible de se connecter. Vérifie le bar ID, le nom et le PIN.')
      }
    } finally {
      setLoading(false)
    }
  }

  if (apiDown) {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#0b0b0f', color: '#fff' }}>
        <div style={{ width: 'min(560px, 92vw)' }}>
          <ApiUnavailable />
        </div>
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#0b0b0f', color: '#fff' }}>
      <form
        onSubmit={onSubmit}
        style={{
          width: 'min(520px, 92vw)',
          border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 16,
          padding: 20,
          background: 'rgba(255,255,255,0.04)',
        }}
      >
        <h1 style={{ margin: 0, fontSize: 26 }}>TORÈ — Portail</h1>
        <p style={{ marginTop: 8, opacity: 0.85 }}>Connexion partenaire (PIN)</p>

        <div style={{ display: 'grid', gap: 12, marginTop: 16 }}>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ opacity: 0.85 }}>Bar ID</span>
            <input
              value={barId}
              onChange={(e) => setBarId(e.target.value.replace(/\D/g, ''))}
              inputMode="numeric"
              required
              style={{ padding: 10, borderRadius: 10, border: '1px solid rgba(255,255,255,0.18)', background: 'transparent', color: '#fff' }}
            />
          </label>

          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ opacity: 0.85 }}>Nom (display_name)</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              style={{ padding: 10, borderRadius: 10, border: '1px solid rgba(255,255,255,0.18)', background: 'transparent', color: '#fff' }}
            />
          </label>

          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ opacity: 0.85 }}>PIN (4 chiffres)</span>
            <input
              value={pin}
              onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
              inputMode="numeric"
              required
              maxLength={4}
              pattern="\d{4}"
              style={{ padding: 10, borderRadius: 10, border: '1px solid rgba(255,255,255,0.18)', background: 'transparent', color: '#fff' }}
            />
          </label>

          {error ? <div style={{ color: '#ffb4b4', fontWeight: 600 }}>{error}</div> : null}

          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '10px 12px',
              borderRadius: 12,
              border: '1px solid rgba(255,255,255,0.18)',
              background: '#ffffff',
              color: '#000',
              fontWeight: 800,
              cursor: 'pointer',
            }}
          >
            {loading ? 'Connexion…' : 'Se connecter'}
          </button>
        </div>
      </form>
    </div>
  )
}
