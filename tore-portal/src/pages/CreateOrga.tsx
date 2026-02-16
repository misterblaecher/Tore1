import React, { useMemo, useState } from 'react'
import Layout from '../ui/Layout'
import { api, ApiError } from '../lib/api'

function idemKey() {
  return `create-orga-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export default function CreateOrga() {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [city, setCity] = useState('')
  const [orgType, setOrgType] = useState('')
  const [websiteUrl, setWebsiteUrl] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<any>(null)
  const [invite, setInvite] = useState<any>(null)
  const requestIdem = useMemo(() => idemKey(), [])

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const created = await api<any>('/orgas', {
        method: 'POST',
        headers: { 'Idempotency-Key': requestIdem },
        body: JSON.stringify({ name, description, city, org_type: orgType, website_url: websiteUrl }),
      })
      setResult(created)
      const inv = await api<any>(`/orgas/${created.orga.id}/invite`)
      setInvite(inv)
    } catch (e: any) {
      if (e instanceof ApiError) {
        setError(e.message)
      } else {
        setError('Erreur inattendue')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Layout title="Create Orga">
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 10, maxWidth: 520 }}>
        <input required placeholder="Nom" value={name} onChange={(e) => setName(e.target.value)} />
        <input placeholder="Description" value={description} onChange={(e) => setDescription(e.target.value)} />
        <input placeholder="Ville" value={city} onChange={(e) => setCity(e.target.value)} />
        <input placeholder="Type" value={orgType} onChange={(e) => setOrgType(e.target.value)} />
        <input placeholder="Website URL" value={websiteUrl} onChange={(e) => setWebsiteUrl(e.target.value)} />
        <button disabled={submitting} type="submit">{submitting ? 'Création…' : 'Créer l’orga'}</button>
      </form>

      {error ? <div style={{ color: '#ff8080', marginTop: 12 }}>{error}</div> : null}

      {result ? (
        <div style={{ marginTop: 16, padding: 12, border: '1px solid #444', borderRadius: 8 }}>
          <div>Organisation créée: <b>{result.orga.name}</b> ({result.role})</div>
          {invite ? (
            <>
              <div style={{ marginTop: 8 }}>
                <a href={invite.deeplink}>Ouvrir dans TORÈ</a>
              </div>
              <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{invite.qr_payload}</pre>
            </>
          ) : null}
        </div>
      ) : null}
    </Layout>
  )
}
