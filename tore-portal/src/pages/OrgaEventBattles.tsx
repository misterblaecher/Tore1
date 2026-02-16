import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout from '../ui/Layout'
import { api } from '../lib/api'

type RoundState = {
  id: number
  title: string
  kind: 'PARTICIPATION' | 'DUEL'
  status: 'IDLE' | 'OPEN' | 'LOCKED'
  optionALabel?: string | null
  optionBLabel?: string | null
  endsAt?: string | null
  winner?: 'A' | 'B' | 'NONE'
}

const blockedReasons = new Set(['event_pause', 'event_menu_only', 'event_degraded', 'event_frozen', 'event_closed'])

export default function OrgaEventBattles() {
  const { eventId } = useParams()
  const [state, setState] = useState<any>(null)
  const [history, setHistory] = useState<any[]>([])
  const [title, setTitle] = useState('Affond round')
  const [kind, setKind] = useState<'PARTICIPATION' | 'DUEL'>('PARTICIPATION')
  const [durationSeconds, setDurationSeconds] = useState(120)
  const [optionALabel, setOptionALabel] = useState('TEAM A')
  const [optionBLabel, setOptionBLabel] = useState('TEAM B')
  const [forceWinner, setForceWinner] = useState<'A' | 'B' | 'NONE'>('NONE')
  const [forceReason, setForceReason] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [runtimeReason, setRuntimeReason] = useState<string>('')
  const [networkMode, setNetworkMode] = useState<'ONLINE' | 'DEGRADED' | 'OFFLINE'>('ONLINE')

  const isOnline = typeof navigator === 'undefined' ? true : navigator.onLine

  const load = async () => {
    if (!eventId) return
    const [statePayload, hist] = await Promise.all([
      api<any>(`/events/${eventId}/battles/state`),
      api<any[]>(`/partner/portal/orga/events/${eventId}/battles/history?limit=10`),
    ])
    setState(statePayload)
    setHistory(hist)
    setRuntimeReason('')
  }

  useEffect(() => {
    load().catch((e: any) => {
      setMessage(e?.message ?? 'Battles indisponible')
      setRuntimeReason(e?.reason || '')
    })
  }, [eventId])

  useEffect(() => {
    const timer = setInterval(() => {
      if (!eventId || !isOnline) return
      load().catch(() => {})
    }, networkMode === 'DEGRADED' ? 5000 : 2000)
    return () => clearInterval(timer)
  }, [eventId, isOnline, networkMode])

  useEffect(() => {
    const onOnline = () => setNetworkMode('ONLINE')
    const onOffline = () => setNetworkMode('OFFLINE')
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [])

  const writeBlocked = !isOnline || blockedReasons.has(runtimeReason)
  const current: RoundState | null = state?.round ?? null
  const countdown = useMemo(() => {
    if (!current?.endsAt) return null
    const ms = new Date(current.endsAt).getTime() - Date.now()
    return Math.max(0, Math.round(ms / 1000))
  }, [current?.endsAt, state?.serverTime])

  async function startRound() {
    if (!eventId || writeBlocked) return
    await api(`/partner/portal/orga/events/${eventId}/battles/rounds/start`, {
      method: 'POST',
      headers: { 'Idempotency-Key': `battles-start-${eventId}-${Date.now()}` },
      body: JSON.stringify({ title, kind, durationSeconds, optionALabel: kind === 'DUEL' ? optionALabel : undefined, optionBLabel: kind === 'DUEL' ? optionBLabel : undefined }),
    })
    setMessage('Round démarré')
    await load()
  }

  async function lockRound() {
    if (!eventId || writeBlocked || !current) return
    await api(`/partner/portal/orga/events/${eventId}/battles/rounds/lock`, {
      method: 'POST', headers: { 'Idempotency-Key': `battles-lock-${current.id}-${Date.now()}` }, body: JSON.stringify({ roundId: current.id }),
    })
    setMessage('Round verrouillé')
    await load()
  }

  async function forceRoundWinner() {
    if (!eventId || writeBlocked || !current || !forceReason.trim()) return
    await api(`/partner/portal/orga/events/${eventId}/battles/rounds/force_winner`, {
      method: 'POST', headers: { 'Idempotency-Key': `battles-force-${current.id}-${Date.now()}` }, body: JSON.stringify({ roundId: current.id, winner: forceWinner, reason: forceReason }),
    })
    setMessage('Winner forcé')
    await load()
  }

  return (
    <Layout title="Battles / Affonds ORGA">
      {message ? <p>{message}</p> : null}
      {!isOnline ? <p style={{ color: '#ffca7a' }}>Offline: lecture cache uniquement, writes bloqués.</p> : null}

      <section style={{ border: '1px solid #30363d', borderRadius: 12, padding: 12, marginBottom: 14 }}>
        <h3>Round actuel</h3>
        {current ? (
          <div style={{ display: 'grid', gap: 6 }}>
            <div><b>{current.title}</b> — {current.kind} — <b>{current.status}</b></div>
            <div>Votes A/B/P: {state?.counts?.A ?? 0} / {state?.counts?.B ?? 0} / {state?.counts?.PARTICIPATE ?? 0}</div>
            <div>Fin: {current.endsAt ? new Date(current.endsAt).toLocaleTimeString() : '—'} {countdown != null ? `(${countdown}s)` : ''}</div>
            <div>Winner: {current.winner ?? 'NONE'}</div>
          </div>
        ) : <p>Aucun round.</p>}
      </section>

      <section style={{ border: '1px solid #30363d', borderRadius: 12, padding: 12, marginBottom: 14, display: 'grid', gap: 8, maxWidth: 680 }}>
        <h3>Démarrer un round</h3>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Titre" />
        <select value={kind} onChange={(e) => setKind(e.target.value as any)}>
          <option value="PARTICIPATION">Participation</option>
          <option value="DUEL">Duel</option>
        </select>
        <input value={durationSeconds} type="number" min={10} max={1800} onChange={(e) => setDurationSeconds(Number(e.target.value || 120))} />
        {kind === 'DUEL' ? (
          <>
            <input value={optionALabel} onChange={(e) => setOptionALabel(e.target.value)} placeholder="Label A" />
            <input value={optionBLabel} onChange={(e) => setOptionBLabel(e.target.value)} placeholder="Label B" />
          </>
        ) : null}
        <button onClick={startRound} disabled={writeBlocked}>Start</button>
      </section>

      <section style={{ border: '1px solid #30363d', borderRadius: 12, padding: 12, marginBottom: 14, display: 'grid', gap: 8, maxWidth: 680 }}>
        <h3>Actions</h3>
        <button onClick={lockRound} disabled={writeBlocked || !current}>Lock round</button>
        <select value={forceWinner} onChange={(e) => setForceWinner(e.target.value as any)}>
          <option value="A">A</option>
          <option value="B">B</option>
          <option value="NONE">NONE</option>
        </select>
        <input value={forceReason} onChange={(e) => setForceReason(e.target.value)} placeholder="Raison obligatoire" />
        <button onClick={forceRoundWinner} disabled={writeBlocked || !current || !forceReason.trim()}>Force winner</button>
      </section>

      <section>
        <h3>Historique (10)</h3>
        <ul>
          {history.map((row) => <li key={row.id}>#{row.id} {row.title} — {row.status} — winner {row.winner} — {row.countsA}/{row.countsB}</li>)}
        </ul>
      </section>
    </Layout>
  )
}
