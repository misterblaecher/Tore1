import React, { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout, { btn, cardStyle, inputStyle } from '../ui/Layout'
import { api, ApiError } from '../lib/api'
import { isApiUnavailable } from '../lib/errors'
import ApiUnavailable from '../ui/ApiUnavailable'

type BetDetailOut = {
  id: number
  scope: string
  event_id?: number | null
  question: string
  kind: string
  status: string
  deadline_at?: string | null
  resolver_user_id?: string | null
  rules_text: string
  dispute_window_minutes: number
  created_by_user_id: string
  created_at?: string | null
  resolved_at?: string | null
  resolved_outcome?: string | null
  pool_yes_tickets: number
  pool_no_tickets: number
  total_pool_tickets: number
  pct_yes: number
  pct_no: number
  positions_count: number
  user_position?: {
    stake_yes: number
    stake_no: number
    stake_total: number
    payout_yes: number
    payout_no: number
  } | null
}

type TimelinePoint = {
  timestamp: string
  pct_yes: number
  total_pool_tickets: number
}

function formatDate(value?: string | null) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString()
}

function makeIdempotencyKey() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `pm-${Date.now()}`
}

export default function PolymarketDetail() {
  const { betId } = useParams()
  const id = Number(betId)

  const [bet, setBet] = useState<BetDetailOut | null>(null)
  const [timeline, setTimeline] = useState<TimelinePoint[]>([])
  const [error, setError] = useState<string | null>(null)
  const [apiDown, setApiDown] = useState(false)
  const [placing, setPlacing] = useState(false)
  const [placeError, setPlaceError] = useState<string | null>(null)
  const [stake, setStake] = useState(10)
  const [side, setSide] = useState<'YES' | 'NO'>('YES')
  const [idemKey, setIdemKey] = useState(makeIdempotencyKey())

  const pctYes = useMemo(() => (bet ? Math.round(bet.pct_yes * 100) : 50), [bet])

  async function load() {
    setApiDown(false)
    setError(null)
    try {
      const data = await api<BetDetailOut>(`/polymarket/bets/${id}`)
      const timelineData = await api<TimelinePoint[]>(`/polymarket/bets/${id}/timeline`)
      setBet(data)
      setTimeline(timelineData)
    } catch (e: any) {
      if (isApiUnavailable(e)) {
        setApiDown(true)
      } else if (e instanceof ApiError) {
        setError(`${e.status ? `HTTP ${e.status}` : 'Erreur'} — ${e.message}`)
      } else {
        setError('Impossible de charger ce marché.')
      }
    }
  }

  useEffect(() => {
    if (!Number.isFinite(id)) return
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  async function submitPosition(e: React.FormEvent) {
    e.preventDefault()
    if (!bet) return
    setPlacing(true)
    setPlaceError(null)
    try {
      await api(`/polymarket/bets/${bet.id}/positions`, {
        method: 'POST',
        body: JSON.stringify({
          side,
          stake_tickets: Number(stake),
          idempotency_key: idemKey,
        }),
      })
      setIdemKey(makeIdempotencyKey())
      await load()
    } catch (e: any) {
      if (e instanceof ApiError) {
        setPlaceError(`${e.status ? `HTTP ${e.status}` : 'Erreur'} — ${e.message}`)
      } else {
        setPlaceError('Impossible de placer la position.')
      }
    } finally {
      setPlacing(false)
    }
  }

  if (apiDown) {
    return (
      <Layout title="Polymarket">
        <ApiUnavailable />
      </Layout>
    )
  }

  return (
    <Layout title="Polymarket">
      {error ? <div style={{ color: '#ffb4b4', fontWeight: 700 }}>{error}</div> : null}

      {bet ? (
        <div style={{ display: 'grid', gap: 16 }}>
          <div style={cardStyle()}>
            <div style={{ fontSize: 22, fontWeight: 800 }}>{bet.question}</div>
            <div style={{ opacity: 0.7, marginTop: 6 }}>
              {bet.kind} • {bet.status}
            </div>
            <div style={{ marginTop: 10, display: 'grid', gap: 6 }}>
              <div>Deadline : {formatDate(bet.deadline_at)}</div>
              <div>Pool total : {bet.total_pool_tickets} tickets</div>
              <div>Participants : {bet.positions_count}</div>
            </div>
            <div style={{ marginTop: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                <span>YES {pctYes}%</span>
                <span>NO {100 - pctYes}%</span>
              </div>
              <div style={{ height: 12, background: 'rgba(255,255,255,0.08)', borderRadius: 999 }}>
                <div
                  style={{
                    width: `${pctYes}%`,
                    height: '100%',
                    background: 'rgba(0,220,120,0.8)',
                    borderRadius: 999,
                  }}
                />
              </div>
            </div>
            {bet.user_position ? (
              <div style={{ marginTop: 12, fontSize: 13, opacity: 0.85 }}>
                <div>Mes tickets YES : {bet.user_position.stake_yes}</div>
                <div>Mes tickets NO : {bet.user_position.stake_no}</div>
                <div>Potentiel YES : {Math.round(bet.user_position.payout_yes)}</div>
                <div>Potentiel NO : {Math.round(bet.user_position.payout_no)}</div>
              </div>
            ) : null}
          </div>

          <form onSubmit={submitPosition} style={{ ...cardStyle(), display: 'grid', gap: 12 }}>
            <div style={{ fontWeight: 800 }}>Placer une position</div>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <label style={{ display: 'grid', gap: 6 }}>
                <span>Side</span>
                <select value={side} onChange={(e) => setSide(e.target.value as 'YES' | 'NO')} style={inputStyle()}>
                  <option value="YES">YES</option>
                  <option value="NO">NO</option>
                </select>
              </label>
              <label style={{ display: 'grid', gap: 6 }}>
                <span>Stake (tickets)</span>
                <input
                  type="number"
                  min={1}
                  value={stake}
                  onChange={(e) => setStake(Number(e.target.value))}
                  style={inputStyle()}
                />
              </label>
            </div>
            <label style={{ display: 'grid', gap: 6 }}>
              <span>Idempotency key</span>
              <input value={idemKey} onChange={(e) => setIdemKey(e.target.value)} style={inputStyle()} />
            </label>
            <button type="submit" style={btn()} disabled={placing}>
              {placing ? 'Envoi…' : 'Placer'}
            </button>
            {placeError ? <div style={{ opacity: 0.85 }}>{placeError}</div> : null}
          </form>

          <div style={cardStyle()}>
            <div style={{ fontWeight: 800, marginBottom: 8 }}>Timeline</div>
            {timeline.length === 0 ? (
              <div style={{ opacity: 0.7 }}>Aucune donnée pour le moment.</div>
            ) : (
              <div style={{ display: 'grid', gap: 6 }}>
                {timeline.map((point, idx) => (
                  <div key={`${point.timestamp}-${idx}`} style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>{formatDate(point.timestamp)}</span>
                    <span>{Math.round(point.pct_yes * 100)}% YES • {point.total_pool_tickets} tickets</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <Link to="/polymarket" style={{ ...btn('ghost'), textDecoration: 'none' }}>
              Retour global
            </Link>
            {bet.event_id ? (
              <Link to={`/events/${bet.event_id}/polymarket`} style={{ ...btn('ghost'), textDecoration: 'none' }}>
                Retour event
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}
    </Layout>
  )
}
