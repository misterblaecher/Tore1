import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../utils/api'
import { setToken } from '../utils/auth'
import { btn, cardStyle, inputStyle } from './Layout'

type AuthOut = { token: string; bar_id: number; role: string; display_name: string }

export default function LoginPage() {
  const nav = useNavigate()
  const [barId, setBarId] = useState('1')
  const [name, setName] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const out = await api<AuthOut>('/partner/auth/login', {
        method: 'POST',
        body: JSON.stringify({ bar_id: Number(barId), display_name: name, pin }),
      })
      setToken(out.token)
      nav('/')
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
              <input value={barId} onChange={(e) => setBarId(e.target.value)} style={inputStyle()} />
            </label>
            <label>
              <div style={{ fontSize: 12, opacity: 0.85, marginBottom: 6 }}>Nom</div>
              <input value={name} onChange={(e) => setName(e.target.value)} style={inputStyle()} />
            </label>
            <label>
              <div style={{ fontSize: 12, opacity: 0.85, marginBottom: 6 }}>PIN (4 chiffres)</div>
              <input value={pin} onChange={(e) => setPin(e.target.value)} style={inputStyle()} inputMode="numeric" maxLength={4} />
            </label>
            {error && <div style={{ color: '#ffb4b4' }}>{error}</div>}
            <button type="submit" disabled={loading} style={btn('primary')}>
              {loading ? 'Connexion…' : 'Se connecter'}
            </button>
            <div style={{ fontSize: 12, opacity: 0.75 }}>
              Astuce dev : pour créer un bar + manager, POST sur <code>/partner/auth/manager/signup</code>.
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
