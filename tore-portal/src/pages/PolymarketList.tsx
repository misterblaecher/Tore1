import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Layout, { btn, cardStyle, inputStyle } from '../ui/Layout'
import { api, ApiError } from '../lib/api'
import { isApiUnavailable } from '../lib/errors'
import ApiUnavailable from '../ui/ApiUnavailable'

type BetOut = {
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
}

const STATUS_OPTIONS = [
  { label: 'Tous', value: '' },
  { label: 'Live', value: 'LIVE' },
  { label: 'Résolus', value: 'RESOLVED' },
  { label: 'Annulés', value: 'CANCELLED' },
]

function formatDate(value?: string | null) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString()
}

function defaultDeadline() {
  const d = new Date()
  d.setHours(d.getHours() + 2)
  return d.toISOString().slice(0, 16)
}

type PolymarketListProps = {
  scope: 'GLOBAL' | 'EVENT'
  title: string
  eventId?: number
}

export default function PolymarketList({ scope, title, eventId }: PolymarketListProps) {
  const [bets, setBets] = useState<BetOut[]>([])
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [apiDown, setApiDown] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [createStatus, setCreateStatus] = useState<string | null>(null)

  const [form, setForm] = useState({
    question: '',
    kind: 'OBJECTIVE',
    deadline_at: defaultDeadline(),
    resolver_user_id: '',
    rules_text: '',
    dispute_window_minutes: 60,
  })

  const query = useMemo(() => {
    const params = new URLSearchParams()
    params.set('scope', scope)
    if (eventId) params.set('event_id', String(eventId))
    if (statusFilter) params.set('status', statusFilter)
    return params.toString()
  }, [eventId, scope, statusFilter])

  async function load() {
    setLoading(true)
    setError(null)
    setApiDown(false)
    try {
      const data = await api<BetOut[]>(`/polymarket/bets?${query}`)
      setBets(data)
    } catch (e: any) {
      if (isApiUnavailable(e)) {
        setApiDown(true)
      } else if (e instanceof ApiError) {
        setError(`${e.status ? `HTTP ${e.status}` : 'Erreur'} — ${e.message}`)
      } else {
        setError('Impossible de charger les marchés.')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query])

  async function submitCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreateStatus(null)
    try {
      const deadline = new Date(form.deadline_at)
      if (Number.isNaN(deadline.getTime())) {
        setCreateStatus('Date limite invalide.')
        return
      }
      await api<BetOut>('/polymarket/bets', {
        method: 'POST',
        body: JSON.stringify({
          scope,
          event_id: eventId ?? null,
          question: form.question.trim(),
          kind: form.kind,
          deadline_at: deadline.toISOString(),
          resolver_user_id: form.resolver_user_id || null,
          rules_text: form.rules_text.trim(),
          dispute_window_minutes: Number(form.dispute_window_minutes),
        }),
      })
      setForm((prev) => ({ ...prev, question: '', rules_text: '' }))
      setCreateStatus('Marché créé avec succès.')
      setShowCreate(false)
      await load()
    } catch (e: any) {
      if (e instanceof ApiError) {
        setCreateStatus(`${e.status ? `HTTP ${e.status}` : 'Erreur'} — ${e.message}`)
      } else {
        setCreateStatus('Impossible de créer le marché.')
      }
    }
  }

  if (apiDown) {
    return (
      <Layout title={title}>
        <ApiUnavailable />
      </Layout>
    )
  }

  return (
    <Layout title={title}>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <label style={{ display: 'grid', gap: 6 }}>
          <span style={{ opacity: 0.8 }}>Filtrer</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ ...inputStyle(), maxWidth: 220 }}
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => setShowCreate((s) => !s)} style={btn()}>
          {showCreate ? 'Fermer' : 'Créer un marché'}
        </button>
        {eventId ? (
          <Link to={`/events/${eventId}`} style={{ ...btn('ghost'), textDecoration: 'none' }}>
            Retour event
          </Link>
        ) : null}
      </div>

      {error ? <div style={{ color: '#ffb4b4', fontWeight: 700, marginTop: 12 }}>{error}</div> : null}
      {loading ? <div style={{ opacity: 0.7, marginTop: 12 }}>Chargement…</div> : null}

      {showCreate ? (
        <form onSubmit={submitCreate} style={{ ...cardStyle(), marginTop: 16, display: 'grid', gap: 12 }}>
          <div style={{ fontWeight: 800 }}>Créer un marché</div>
          <label style={{ display: 'grid', gap: 6 }}>
            <span>Question</span>
            <input
              value={form.question}
              onChange={(e) => setForm((prev) => ({ ...prev, question: e.target.value }))}
              style={inputStyle()}
              placeholder="Ex: L'équipe va gagner ?"
              required
            />
          </label>
          <div style={{ display: 'grid', gap: 6 }}>
            <span>Type</span>
            <select
              value={form.kind}
              onChange={(e) => setForm((prev) => ({ ...prev, kind: e.target.value }))}
              style={inputStyle()}
            >
              <option value="OBJECTIVE">OBJECTIVE</option>
              <option value="SUBJECTIVE">SUBJECTIVE</option>
            </select>
          </div>
          <label style={{ display: 'grid', gap: 6 }}>
            <span>Date limite</span>
            <input
              type="datetime-local"
              value={form.deadline_at}
              onChange={(e) => setForm((prev) => ({ ...prev, deadline_at: e.target.value }))}
              style={inputStyle()}
              required
            />
          </label>
          {form.kind === 'SUBJECTIVE' ? (
            <label style={{ display: 'grid', gap: 6 }}>
              <span>Resolver user id</span>
              <input
                value={form.resolver_user_id}
                onChange={(e) => setForm((prev) => ({ ...prev, resolver_user_id: e.target.value }))}
                style={inputStyle()}
                placeholder="UUID"
                required
              />
            </label>
          ) : null}
          <label style={{ display: 'grid', gap: 6 }}>
            <span>Rules</span>
            <textarea
              value={form.rules_text}
              onChange={(e) => setForm((prev) => ({ ...prev, rules_text: e.target.value }))}
              style={{ ...inputStyle(), minHeight: 90 }}
              required
            />
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span>Fenêtre dispute (minutes)</span>
            <input
              type="number"
              min={1}
              max={1440}
              value={form.dispute_window_minutes}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, dispute_window_minutes: Number(e.target.value) }))
              }
              style={inputStyle()}
            />
          </label>
          <button type="submit" style={btn()}>
            Créer
          </button>
          {createStatus ? <div style={{ opacity: 0.85 }}>{createStatus}</div> : null}
        </form>
      ) : null}

      <div style={{ display: 'grid', gap: 12, marginTop: 16 }}>
        {bets.map((bet) => (
          <Link
            key={bet.id}
            to={`/polymarket/${bet.id}`}
            style={{ ...cardStyle(), textDecoration: 'none', color: 'inherit' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <div>
                <div style={{ fontWeight: 800, fontSize: 18 }}>{bet.question}</div>
                <div style={{ opacity: 0.7, marginTop: 4 }}>
                  {bet.kind} • {bet.status}
                </div>
              </div>
              <div style={{ textAlign: 'right', opacity: 0.8 }}>
                <div>YES {Math.round(bet.pct_yes * 100)}%</div>
                <div>Pool {bet.total_pool_tickets} tickets</div>
              </div>
            </div>
            <div style={{ marginTop: 8, opacity: 0.75 }}>
              Deadline : {formatDate(bet.deadline_at)}
            </div>
          </Link>
        ))}
        {!loading && bets.length === 0 ? (
          <div style={{ opacity: 0.75 }}>Aucun marché pour le moment.</div>
        ) : null}
      </div>
    </Layout>
  )
}
