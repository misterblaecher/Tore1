import React, { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { setToken, setSession } from '../lib/auth'
import { btn, cardStyle, inputStyle } from './Layout'

type AuthOut = { token: string; bar_id: number; role: string; display_name: string }

export default function LoginPage() {
  const nav = useNavigate()
  const location = useLocation()
  const [barId, setBarId] = useState('')
  const [name, setName] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (loading) return
    setError(null)
    setLoading(true)
    try {
      const out = await api<AuthOut>('/partner/auth/login', {
        method: 'POST',
        body: JSON.stringify({ bar_id: Number(barId), display_name: name, pin }),
      })
      if (!out.token || !out.role || !out.bar_id) throw new Error('Réponse de connexion invalide')
      setToken(out.token)
      setSession({ bar_id: out.bar_id, display_name: out.display_name, role: out.role })
      const from = (location.state as { from?: string } | null)?.from
      nav(from?.startsWith('/') && !from.startsWith('//') ? from : '/', { replace: true })
    } catch (err: any) {
      setError(err?.message ?? 'Erreur')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#0b0f14', color: '#e9eef6' }}>
      <div style={{ width: 'min(520px, 92vw)' }}>
        <h1 style={{ margin: 0, fontSize: 28, letterSpacing: 0.5 }}>TORÈ — Portail</h1>
        <p style={{ marginTop: 8, opacity: 0.8 }}>Connexion partenaire (bar / staff).</p>
        <div style={cardStyle()}>
          <form onSubmit={onSubmit} style={{ display: 'grid', gap: 12 }}>
            <label>
              <div style={{ fontSize: 12, opacity: 0.85, marginBottom: 6 }}>Bar ID</div>
              <input required type="number" min="1" value={barId} onChange={(e) => setBarId(e.target.value)} style={inputStyle()} />
            </label>
            <label>
              <div style={{ fontSize: 12, opacity: 0.85, marginBottom: 6 }}>Nom</div>
              <input required minLength={2} autoComplete="username" value={name} onChange={(e) => setName(e.target.value)} style={inputStyle()} />
            </label>
            <label>
              <div style={{ fontSize: 12, opacity: 0.85, marginBottom: 6 }}>PIN (4 chiffres)</div>
              <input required type="password" pattern="[0-9]{4}" autoComplete="current-password" value={pin} onChange={(e) => setPin(e.target.value)} style={inputStyle()} inputMode="numeric" maxLength={4} />
            </label>
            {error && <div style={{ color: '#ffb4b4' }}>{error}</div>}
            <button type="submit" disabled={loading} style={btn('primary')}>
              {loading ? 'Connexion…' : 'Se connecter'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
