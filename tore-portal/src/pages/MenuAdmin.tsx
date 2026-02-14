import React, { useEffect, useMemo, useState } from 'react'
import Layout, { btn, cardStyle, inputStyle } from '../ui/Layout'
import { useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { EmptyState, InlineAlert } from '../lib/ui'

type MenuItem = {
  id: number
  name: string
  price_cents: number
  is_active: boolean
  is_available: boolean
}

type MenuCategory = {
  id: number
  name: string
  sort_order: number
  is_active: boolean
  items: MenuItem[]
}

type Snapshot = {
  event_state: 'LIVE' | 'PAUSE' | 'MENU_ONLY' | 'CLOSED' | 'SCHEDULED'
  modules: Record<string, { effective_state: 'ON' | 'OFF' | 'READ_ONLY' }>
}

const PAGE_SIZE = 4

export default function MenuAdmin() {
  const [params] = useSearchParams()
  const [categories, setCategories] = useState<MenuCategory[]>([])
  const [categoryName, setCategoryName] = useState('')
  const [newItems, setNewItems] = useState<Record<number, { name: string; price_cents: number }>>({})
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)

  const eventId = Number(params.get('event_id') || 0)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const rows = await api<MenuCategory[]>('/partner/portal/menu')
      setCategories(rows)
      if (eventId) {
        const snap = await api<Snapshot>(`/partner/portal/event/${eventId}/state-snapshot`)
        setSnapshot(snap)
      }
    } catch (e: any) {
      setError(e?.message || 'Chargement menu impossible')
      setCategories([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [eventId])

  const menuRuntimeState = snapshot?.modules?.orders_enabled?.effective_state || 'ON'
  const disabledByRuntime = menuRuntimeState !== 'ON'

  const createCategory = async () => {
    if (!categoryName.trim() || disabledByRuntime) return
    await api('/partner/portal/menu/categories', {
      method: 'POST',
      body: JSON.stringify({ name: categoryName, sort_order: categories.length + 1, is_active: true }),
    })
    setCategoryName('')
    void load()
  }

  const createItem = async (categoryId: number) => {
    const data = newItems[categoryId]
    if (!data?.name || disabledByRuntime) return
    await api('/partner/portal/menu/items', {
      method: 'POST',
      body: JSON.stringify({ category_id: categoryId, name: data.name, description: '', price_cents: Number(data.price_cents || 0) }),
    })
    setNewItems((prev) => ({ ...prev, [categoryId]: { name: '', price_cents: 0 } }))
    void load()
  }

  const patchItem = async (item: MenuItem, patch: Partial<MenuItem>) => {
    if (disabledByRuntime) return
    await api(`/partner/portal/menu/items/${item.id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    })
    void load()
  }

  const pagedCategories = useMemo(() => categories.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE), [categories, page])
  const maxPage = Math.max(1, Math.ceil(categories.length / PAGE_SIZE))

  return (
    <Layout title="Menu (admin)">
      {disabledByRuntime ? <InlineAlert tone="warning">Runtime {snapshot?.event_state || 'event'} → actions menu bloquées ({menuRuntimeState}).</InlineAlert> : null}
      {error ? <InlineAlert tone="error">{error}</InlineAlert> : null}
      <div style={{ ...cardStyle(), display: 'grid', gap: 10 }}>
        <h3>Ajouter une catégorie</h3>
        <input disabled={disabledByRuntime} value={categoryName} onChange={(e) => setCategoryName(e.target.value)} style={inputStyle()} placeholder="Ex: Cocktails" />
        <button disabled={disabledByRuntime} style={btn()} onClick={createCategory}>Créer</button>
      </div>

      {loading ? <div style={{ marginTop: 12 }}>Chargement…</div> : null}
      {!loading && categories.length === 0 ? <EmptyState title="Aucune catégorie" body="Crée une catégorie pour démarrer." /> : null}

      <div style={{ marginTop: 16, display: 'grid', gap: 12 }}>
        {pagedCategories.map((category) => (
          <div key={category.id} style={cardStyle()}>
            <div style={{ fontWeight: 800 }}>{category.name}</div>
            <div style={{ marginTop: 10, display: 'grid', gap: 8 }}>
              {category.items.map((item) => (
                <div key={item.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <div>{item.name} — {(item.price_cents / 100).toFixed(2)}€</div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button disabled={disabledByRuntime} style={btn('ghost')} onClick={() => void patchItem(item, { is_available: !item.is_available })}>
                      dispo: {item.is_available ? 'ON' : 'OFF'}
                    </button>
                    <button disabled={disabledByRuntime} style={btn('ghost')} onClick={() => void patchItem(item, { is_active: !item.is_active })}>
                      actif: {item.is_active ? 'ON' : 'OFF'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
              <input
                style={inputStyle()}
                placeholder="Nom article"
                value={newItems[category.id]?.name || ''}
                onChange={(e) => setNewItems((prev) => ({ ...prev, [category.id]: { name: e.target.value, price_cents: prev[category.id]?.price_cents || 0 } }))}
              />
              <input
                style={{ ...inputStyle(), maxWidth: 120 }}
                type="number"
                placeholder="Prix cts"
                value={newItems[category.id]?.price_cents || 0}
                onChange={(e) => setNewItems((prev) => ({ ...prev, [category.id]: { name: prev[category.id]?.name || '', price_cents: Number(e.target.value || 0) } }))}
              />
              <button disabled={disabledByRuntime} style={btn()} onClick={() => void createItem(category.id)}>Ajouter</button>
            </div>
          </div>
        ))}
      </div>

      {categories.length > PAGE_SIZE ? (
        <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>←</button>
          <span>Page {page}/{maxPage}</span>
          <button onClick={() => setPage((p) => Math.min(maxPage, p + 1))} disabled={page >= maxPage}>→</button>
        </div>
      ) : null}
    </Layout>
  )
}
