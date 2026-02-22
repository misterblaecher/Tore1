import React, { useEffect, useMemo, useState } from 'react'
import Layout, { btn, cardStyle, inputStyle } from '../ui/Layout'
import { api, apiText, ApiError } from '../lib/api'
import { isApiUnavailable } from '../lib/errors'
import ApiUnavailable from '../ui/ApiUnavailable'

type Scope = 'global' | 'event'
type StatusFilter = 'live' | 'resolved' | 'cancelled'

type MarketLite = {
  id: number
  question: string
  status: string
  scope: string
  yes_price: number
  no_price: number
  volume: number
  event_id?: number | null
}

type MarketsResponse = {
  items: MarketLite[]
  next_cursor?: string | null
}

type Snapshot = {
  event_state?: string
  modules?: Record<string, { effective_state?: 'ON' | 'OFF' | 'READ_ONLY'; reason?: string | null }>
}

const STATUS_OPTIONS: Array<{ label: string; value: StatusFilter }> = [
  { label: 'Live', value: 'live' },
  { label: 'Resolved', value: 'resolved' },
  { label: 'Cancelled', value: 'cancelled' },
]

function reasonMessage(reason?: string) {
  switch (reason) {
    case 'event_paused':
      return 'Event en pause. Actions admin bloquées.'
    case 'module_off':
      return 'Module Polymarket désactivé.'
    case 'revoked':
      return 'Accès révoqué. Actions admin bloquées.'
    case 'rate_limited':
      return 'Trop de requêtes. Attends un instant.'
    case 'forbidden':
      return 'Action non autorisée.'
    case 'already_resolved':
      return 'Marché déjà résolu.'
    default:
      return null
  }
}

function statusBadge(status: string) {
  const normalized = status.toLowerCase()
  if (normalized === 'live') return 'LIVE'
  if (normalized === 'resolved' || normalized === 'finalized' || normalized === 'resolved_pending') return 'RESOLVED'
  if (normalized === 'cancelled') return 'CANCELLED'
  return status.toUpperCase()
}

function triggerCsvDownload(csvText: string, filename: string) {
  const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export default function PolymarketAdmin() {
  const [scope, setScope] = useState<Scope>('global')
  const [eventIdInput, setEventIdInput] = useState('')
  const [status, setStatus] = useState<StatusFilter>('live')

  const [items, setItems] = useState<MarketLite[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [cursorStack, setCursorStack] = useState<Array<string | null>>([null])
  const [loading, setLoading] = useState(false)
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null)
  const [apiDown, setApiDown] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [runtimeReason, setRuntimeReason] = useState<string | null>(null)
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [disputeNoteById, setDisputeNoteById] = useState<Record<number, string>>({})
  const [resolveOutcomeById, setResolveOutcomeById] = useState<Record<number, 'YES' | 'NO'>>({})

  const [exportLoading, setExportLoading] = useState<'markets' | 'positions' | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)

  const eventId = useMemo(() => {
    const parsed = Number(eventIdInput)
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null
  }, [eventIdInput])

  const moduleState = snapshot?.modules?.polymarket_enabled?.effective_state || 'ON'
  const stateReason = moduleState === 'OFF' ? 'module_off' : moduleState === 'READ_ONLY' ? 'event_paused' : null
  const writeBlocked = !!stateReason || runtimeReason === 'event_paused' || runtimeReason === 'module_off' || runtimeReason === 'revoked' || runtimeReason === 'rate_limited'

  const currentCursor = cursorStack[cursorStack.length - 1] ?? null

  async function loadPage(cursor: string | null, resetStack = false) {
    setLoading(true)
    setError(null)
    setApiDown(false)
    setRuntimeReason(null)

    const params = new URLSearchParams()
    params.set('scope', scope)
    params.set('status', status)
    if (scope === 'event' && eventId) {
      params.set('event_id', String(eventId))
    }
    if (cursor) params.set('cursor', cursor)
    params.set('limit', '25')

    try {
      const data = await api<MarketsResponse>(`/polymarket/markets?${params.toString()}`)
      const seen = new Set<number>()
      const deduped = (data.items || []).filter((m) => {
        if (seen.has(m.id)) return false
        seen.add(m.id)
        return true
      })
      setItems(deduped)
      setNextCursor(data.next_cursor ?? null)
      if (resetStack) {
        setCursorStack([cursor])
      }
    } catch (e) {
      if (isApiUnavailable(e)) {
        setApiDown(true)
      } else if (e instanceof ApiError) {
        if (e.reason) {
          setRuntimeReason(e.reason)
          setError(reasonMessage(e.reason) ?? e.message)
        } else {
          setError(e.message)
        }
      } else {
        setError('Impossible de charger les marchés.')
      }
    } finally {
      setLoading(false)
    }
  }


  useEffect(() => {
    if (scope !== 'event' || !eventId) {
      setSnapshot(null)
      return
    }
    api<Snapshot>(`/partner/portal/event/${eventId}/state-snapshot`).then(setSnapshot).catch(() => setSnapshot(null))
  }, [scope, eventId])

  useEffect(() => {
    setCursorStack([null])
    setNextCursor(null)
    loadPage(null, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, status, eventId])

  async function runAction(marketId: number, kind: 'resolve' | 'finalize' | 'dispute' | 'cancel') {
    if (writeBlocked) return
    setActionLoadingId(marketId)
    setError(null)
    setRuntimeReason(null)

    try {
      if (kind === 'resolve') {
        const outcome = resolveOutcomeById[marketId] ?? 'YES'
        await api('/polymarket/resolve', {
          method: 'POST',
          body: JSON.stringify({ market_id: marketId, outcome }),
        })
      } else if (kind === 'finalize') {
        await api('/polymarket/finalize', {
          method: 'POST',
          body: JSON.stringify({ market_id: marketId }),
        })
      } else if (kind === 'dispute') {
        const note = (disputeNoteById[marketId] || '').trim()
        if (!note || note.length < 3) {
          setError('Note de dispute trop courte (min 3 caractères).')
          return
        }
        await api('/polymarket/dispute', {
          method: 'POST',
          body: JSON.stringify({ market_id: marketId, note }),
        })
      } else {
        await api('/polymarket/cancel', {
          method: 'POST',
          body: JSON.stringify({ market_id: marketId, reason: 'admin_cancel' }),
        })
      }
      await loadPage(currentCursor, false)
    } catch (e) {
      if (e instanceof ApiError) {
        const msg = reasonMessage(e.reason) ?? e.message
        setError(msg)
        if (e.reason === 'event_paused' || e.reason === 'module_off' || e.reason === 'revoked' || e.reason === 'rate_limited') {
          setRuntimeReason(e.reason)
        }
      } else {
        setError('Action impossible pour ce marché.')
      }
    } finally {
      setActionLoadingId(null)
    }
  }

  async function downloadExport(kind: 'markets' | 'positions') {
    setExportLoading(kind)
    setExportError(null)
    const params = new URLSearchParams()
    params.set('scope', scope)
    if (scope === 'event' && eventId) params.set('event_id', String(eventId))
    if (kind === 'markets') params.set('status', status)

    try {
      const csv = await apiText(`/polymarket/exports/${kind}.csv?${params.toString()}`)
      triggerCsvDownload(csv, `${kind}-${scope}-${Date.now()}.csv`)
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.reason === 'rate_limited') {
          setExportError('Téléchargement limité temporairement (cooldown).')
          setRuntimeReason('rate_limited')
        } else {
          setExportError(reasonMessage(e.reason) ?? e.message)
        }
      } else {
        setExportError('Impossible de télécharger le CSV.')
      }
    } finally {
      setExportLoading(null)
    }
  }

  if (apiDown) {
    return (
      <Layout title="Polymarket Admin ULTRA">
        <ApiUnavailable />
      </Layout>
    )
  }

  return (
    <Layout title="Polymarket Admin ULTRA">
      <div style={{ ...cardStyle(), display: 'grid', gap: 12, marginBottom: 16 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <button type="button" style={scope === 'global' ? btn() : btn('ghost')} onClick={() => setScope('global')}>
            GLOBAL
          </button>
          <button type="button" style={scope === 'event' ? btn() : btn('ghost')} onClick={() => setScope('event')}>
            EVENT
          </button>
        </div>

        {scope === 'event' ? (
          <label style={{ display: 'grid', gap: 6, maxWidth: 220 }}>
            <span>Event ID</span>
            <input
              type="number"
              min={1}
              value={eventIdInput}
              onChange={(e) => setEventIdInput(e.target.value)}
              style={inputStyle()}
              placeholder="Ex: 42"
            />
          </label>
        ) : null}

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {STATUS_OPTIONS.map((s) => (
            <button
              key={s.value}
              type="button"
              style={status === s.value ? btn() : btn('ghost')}
              onClick={() => setStatus(s.value)}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            type="button"
            style={btn('ghost')}
            onClick={() => downloadExport('markets')}
            disabled={exportLoading !== null}
          >
            {exportLoading === 'markets' ? 'Téléchargement…' : 'Download markets.csv'}
          </button>
          <button
            type="button"
            style={btn('ghost')}
            onClick={() => downloadExport('positions')}
            disabled={exportLoading !== null}
          >
            {exportLoading === 'positions' ? 'Téléchargement…' : 'Download positions.csv'}
          </button>
        </div>
      </div>

      {scope === 'event' && eventId ? <div style={{ ...cardStyle(), marginBottom: 12 }}>Event state: {snapshot?.event_state || 'LIVE'}</div> : null}
      {stateReason === 'module_off' ? <div style={{ ...cardStyle(), marginBottom: 12 }}>Module désactivé</div> : null}
      {runtimeReason ? (
        <div
          style={{
            ...cardStyle(),
            marginBottom: 12,
            borderColor: 'rgba(255,170,0,0.7)',
            background: 'rgba(255,170,0,0.15)',
            fontWeight: 700,
          }}
        >
          {reasonMessage(runtimeReason) ?? `Runtime: ${runtimeReason}`}
        </div>
      ) : null}

      {error ? <div style={{ color: '#ffb4b4', fontWeight: 700, marginBottom: 12 }}>{error}</div> : null}
      {exportError ? <div style={{ color: '#ffd1a8', marginBottom: 12 }}>{exportError}</div> : null}
      {loading ? <div style={{ opacity: 0.8, marginBottom: 10 }}>Chargement des marchés…</div> : null}

      <div style={{ display: 'grid', gap: 10 }}>
        {items.map((market) => {
          const resolveOutcome = resolveOutcomeById[market.id] ?? 'YES'
          const disputeNote = disputeNoteById[market.id] ?? ''
          const rowBusy = actionLoadingId === market.id
          const disabled = writeBlocked || rowBusy

          return (
            <div key={market.id} style={{ ...cardStyle(), display: 'grid', gap: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <div>
                  <div style={{ fontWeight: 800 }}>#{market.id} {market.question}</div>
                  <div style={{ opacity: 0.75, marginTop: 4 }}>
                    {market.scope.toUpperCase()} • {statusBadge(market.status)}
                    {market.event_id ? ` • EVENT ${market.event_id}` : ''}
                  </div>
                </div>
                <div style={{ textAlign: 'right', opacity: 0.9 }}>
                  <div>YES {Math.round((market.yes_price ?? 0.5) * 100)}%</div>
                  <div>NO {Math.round((market.no_price ?? 0.5) * 100)}%</div>
                  <div>Volume {market.volume ?? 0}</div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                <select
                  value={resolveOutcome}
                  onChange={(e) =>
                    setResolveOutcomeById((prev) => ({ ...prev, [market.id]: e.target.value as 'YES' | 'NO' }))
                  }
                  style={{ ...inputStyle(), width: 120 }}
                >
                  <option value="YES">YES</option>
                  <option value="NO">NO</option>
                </select>
                <button type="button" style={btn()} onClick={() => runAction(market.id, 'resolve')} disabled={disabled}>
                  Resolve
                </button>
                <button type="button" style={btn('ghost')} onClick={() => runAction(market.id, 'finalize')} disabled={disabled}>
                  Finalize
                </button>
                <button type="button" style={btn('ghost')} onClick={() => runAction(market.id, 'cancel')} disabled={disabled}>
                  Cancel
                </button>
              </div>

              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <input
                  value={disputeNote}
                  onChange={(e) => setDisputeNoteById((prev) => ({ ...prev, [market.id]: e.target.value }))}
                  placeholder="Dispute note"
                  style={{ ...inputStyle(), minWidth: 200, flex: 1 }}
                />
                <button type="button" style={btn('ghost')} onClick={() => runAction(market.id, 'dispute')} disabled={disabled}>
                  Dispute
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {!loading && items.length === 0 ? <div style={{ opacity: 0.75 }}>Aucun marché trouvé.</div> : null}

      <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
        <button
          type="button"
          style={btn('ghost')}
          disabled={loading || cursorStack.length <= 1}
          onClick={async () => {
            if (cursorStack.length <= 1) return
            const prevStack = cursorStack.slice(0, -1)
            const prevCursor = prevStack[prevStack.length - 1] ?? null
            setCursorStack(prevStack)
            await loadPage(prevCursor, false)
          }}
        >
          ← Prev
        </button>
        <button
          type="button"
          style={btn('ghost')}
          disabled={loading || !nextCursor}
          onClick={async () => {
            if (!nextCursor) return
            const nextStack = [...cursorStack, nextCursor]
            setCursorStack(nextStack)
            await loadPage(nextCursor, false)
          }}
        >
          Next →
        </button>
      </div>
    </Layout>
  )
}
