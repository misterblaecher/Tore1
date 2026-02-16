import { FormEvent, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { API_BASE, ApiError } from '../lib/api'
import { setToken } from '../lib/auth'

type RequestOut = { token?: string; dev_token?: string }
type VerifyOut = { access_token?: string; accessToken?: string }

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | undefined)?.from || '/create-orga'
  const isDev = useMemo(() => import.meta.env.DEV, [])

  const [email, setEmail] = useState('')
  const [token, setMagicToken] = useState('')
  const [devToken, setDevToken] = useState<string | null>(null)
  const [step, setStep] = useState<'request' | 'verify'>('request')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function requestLink(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/auth/email/request_link`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      if (!res.ok) throw new ApiError(`HTTP ${res.status}`)
      const data = (await res.json()) as RequestOut
      setDevToken(isDev ? data.token ?? data.dev_token ?? null : null)
      setStep('verify')
    } catch {
      setError('Impossible d’envoyer le lien pour le moment.')
    } finally {
      setLoading(false)
    }
  }

  async function verifyToken(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/auth/email/verify_link`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, token }),
      })
      if (!res.ok) throw new ApiError(`HTTP ${res.status}`)
      const data = (await res.json()) as VerifyOut
      const accessToken = data.access_token ?? data.accessToken
      if (!accessToken) throw new Error('missing token')
      setToken(accessToken)
      navigate(from, { replace: true })
    } catch {
      setError('Code invalide ou expiré.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#0a0b10', color: '#fff' }}>
      <div style={{ width: '100%', maxWidth: 420, padding: 20, borderRadius: 16, background: 'rgba(255,255,255,0.04)' }}>
        <h1>Connexion</h1>
        <button type="button" style={{ width: '100%', padding: 10, borderRadius: 10, marginBottom: 12 }}>
          Continuer avec Google (bientôt)
        </button>

        {step === 'request' ? (
          <form onSubmit={requestLink} style={{ display: 'grid', gap: 10 }}>
            <input value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="email@exemple.com" />
            <button type="submit" disabled={loading}>{loading ? 'Envoi…' : 'Recevoir un lien magique'}</button>
          </form>
        ) : (
          <form onSubmit={verifyToken} style={{ display: 'grid', gap: 10 }}>
            <p>Check your email.</p>
            {isDev && devToken ? <code>DEV token: {devToken}</code> : null}
            <input value={token} onChange={(e) => setMagicToken(e.target.value)} required placeholder="Token" />
            <button type="submit" disabled={loading}>{loading ? 'Vérification…' : 'Verify'}</button>
            <button type="button" onClick={() => setStep('request')}>Renvoyer un lien</button>
          </form>
        )}

        {error ? <p style={{ color: '#ffb4b4' }}>{error}</p> : null}
      </div>
    </div>
  )
}
