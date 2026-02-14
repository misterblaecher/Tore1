import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'
import { Button, Card, InlineAlert } from '../lib/ui'

const moduleKeys = ['menu', 'wallet', 'ticker', 'entry', 'broadcast', 'music', 'vote', 'polymarket', 'hunt', 'battles', 'wifi', 'safety'] as const

type Template = {
  id: string
  name: string
  defaultModulesOn: Record<string, boolean>
  defaultRules: Record<string, any>
  durationPreset: string
}

export default function CreateEventWizard() {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [name, setName] = useState('')
  const [venue, setVenue] = useState('')
  const [startAt, setStartAt] = useState('')
  const [endAt, setEndAt] = useState('')
  const [templates, setTemplates] = useState<Template[]>([])
  const [templateId, setTemplateId] = useState('')
  const [modulesOn, setModulesOn] = useState<Record<string, boolean>>({ menu: true, wallet: true, ticker: true })
  const [rulesFlags, setRulesFlags] = useState<Record<string, any>>({ charter_enabled: true, require_charter_accept: false })
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [isOnline, setIsOnline] = useState<boolean>(typeof navigator === 'undefined' ? true : navigator.onLine)
  const [eventState, setEventState] = useState<'LIVE' | 'DEGRADED'>('LIVE')

  useEffect(() => {
    const onOnline = () => setIsOnline(true)
    const onOffline = () => setIsOnline(false)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [])

  useEffect(() => {
    api<Template[]>('/partner/portal/orga/event_templates')
      .then((items) => setTemplates(items || []))
      .catch(() => setTemplates([]))

    api<any>('/partner/portal/orga/events/active')
      .then((snap) => {
        if (snap?.event_state === 'DEGRADED') setEventState('DEGRADED')
      })
      .catch(() => {})
  }, [])

  const networkMode = useMemo<'ONLINE' | 'OFFLINE' | 'DEGRADED'>(() => {
    if (!isOnline) return 'OFFLINE'
    if (eventState === 'DEGRADED') return 'DEGRADED'
    return 'ONLINE'
  }, [isOnline, eventState])

  const writeDisabledReason = useMemo(() => {
    if (networkMode === 'OFFLINE') return 'Write gate: offline'
    if (networkMode === 'DEGRADED') return 'Write gate: event runtime degraded'
    return ''
  }, [networkMode])

  const basicsValid = Boolean(name.trim() && venue.trim() && startAt && endAt && new Date(endAt) > new Date(startAt))

  const applyTemplate = (id: string) => {
    setTemplateId(id)
    const tpl = templates.find((item) => item.id === id)
    if (!tpl) return
    setModulesOn({ ...tpl.defaultModulesOn })
    setRulesFlags({ ...tpl.defaultRules })
  }

  const createEvent = async () => {
    if (!basicsValid || networkMode !== 'ONLINE') return
    setLoading(true)
    setError(null)
    const idem = `create-event-${Date.now()}`
    try {
      const event = await api<any>('/partner/portal/orga/events', {
        method: 'POST',
        headers: { 'Idempotency-Key': idem },
        body: JSON.stringify({
          name,
          venue,
          startAt: new Date(startAt).toISOString(),
          endAt: new Date(endAt).toISOString(),
          timezone: 'Europe/Brussels',
          templateId: templateId || null,
          modulesOn,
          rulesFlags,
        }),
      })
      await api(`/partner/portal/orga/events/${event.id}/qr_pack`, {
        method: 'POST',
        headers: { 'Idempotency-Key': `${idem}-qr` },
      })
      navigate(`/orga/events/${event.id}/qr-pack`)
    } catch (e: any) {
      setError(e?.message ?? 'Impossible de créer l’event.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout title="Créer Event (~60s)">
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      {networkMode !== 'ONLINE' ? <InlineAlert tone="warning">{writeDisabledReason}. Aucune action de création n’est autorisée.</InlineAlert> : null}
      <Card>
        <strong>Step {step}/3</strong>
        {step === 1 ? (
          <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
            <input placeholder="Nom event" value={name} onChange={(e) => setName(e.target.value)} />
            <input placeholder="Lieu" value={venue} onChange={(e) => setVenue(e.target.value)} />
            <label>Start</label>
            <input type="datetime-local" value={startAt} onChange={(e) => setStartAt(e.target.value)} />
            <label>End</label>
            <input type="datetime-local" value={endAt} onChange={(e) => setEndAt(e.target.value)} />
            {!basicsValid ? <small style={{ color: '#ff7a7a' }}>Remplis tous les champs + plage horaire valide.</small> : null}
          </div>
        ) : null}

        {step === 2 ? (
          <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
            <select value={templateId} onChange={(e) => applyTemplate(e.target.value)}>
              <option value="">Template rapide</option>
              {templates.map((tpl) => <option key={tpl.id} value={tpl.id}>{tpl.name} ({tpl.durationPreset})</option>)}
            </select>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 6 }}>
              {moduleKeys.map((key) => (
                <label key={key}>
                  <input type="checkbox" checked={Boolean(modulesOn[key])} onChange={(e) => setModulesOn((prev) => ({ ...prev, [key]: e.target.checked }))} /> {key}
                </label>
              ))}
            </div>
          </div>
        ) : null}

        {step === 3 ? (
          <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
            <label>
              <input type="checkbox" checked={Boolean(rulesFlags.charter_enabled)} onChange={(e) => setRulesFlags((prev) => ({ ...prev, charter_enabled: e.target.checked }))} /> Charter enabled
            </label>
            <label>
              <input type="checkbox" checked={Boolean(rulesFlags.require_charter_accept)} onChange={(e) => setRulesFlags((prev) => ({ ...prev, require_charter_accept: e.target.checked }))} /> Require charter accept
            </label>
            <Button onClick={createEvent} disabled={loading || !basicsValid || networkMode !== 'ONLINE'}>{loading ? 'Création…' : 'Créer & générer QR'}</Button>
          </div>
        ) : null}

        <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
          <Button variant="secondary" onClick={() => setStep((prev) => Math.max(1, prev - 1))} disabled={step === 1}>Retour</Button>
          <Button onClick={() => setStep((prev) => Math.min(3, prev + 1))} disabled={step === 3 || (step === 1 && !basicsValid)}>Suivant</Button>
        </div>
      </Card>
    </Layout>
  )
}
