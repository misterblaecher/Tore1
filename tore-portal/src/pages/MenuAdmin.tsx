import React, { useEffect, useState } from 'react'
import Layout, { btn, cardStyle, inputStyle } from '../ui/Layout'
import { api } from '../lib/api'

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

export default function MenuAdmin() {
  const [categories, setCategories] = useState<MenuCategory[]>([])
  const [categoryName, setCategoryName] = useState('')
  const [newItems, setNewItems] = useState<Record<number, { name: string; price_cents: number }>>({})

  const load = async () => {
    const rows = await api<MenuCategory[]>('/partner/portal/menu')
    setCategories(rows)
  }

  useEffect(() => {
    load()
  }, [])

  const createCategory = async () => {
    if (!categoryName.trim()) return
    await api('/partner/portal/menu/categories', {
      method: 'POST',
      body: JSON.stringify({ name: categoryName, sort_order: categories.length + 1, is_active: true }),
    })
    setCategoryName('')
    load()
  }

  const createItem = async (categoryId: number) => {
    const data = newItems[categoryId]
    if (!data?.name) return
    await api('/partner/portal/menu/items', {
      method: 'POST',
      body: JSON.stringify({ category_id: categoryId, name: data.name, description: '', price_cents: Number(data.price_cents || 0) }),
    })
    setNewItems((prev) => ({ ...prev, [categoryId]: { name: '', price_cents: 0 } }))
    load()
  }

  const patchItem = async (item: MenuItem, patch: Partial<MenuItem>) => {
    await api(`/partner/portal/menu/items/${item.id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    })
    load()
  }

  return (
    <Layout title="Menu (admin)">
      <div style={{ ...cardStyle(), display: 'grid', gap: 10 }}>
        <h3>Ajouter une catégorie</h3>
        <input value={categoryName} onChange={(e) => setCategoryName(e.target.value)} style={inputStyle()} placeholder="Ex: Cocktails" />
        <button style={btn()} onClick={createCategory}>Créer</button>
      </div>

      <div style={{ marginTop: 16, display: 'grid', gap: 12 }}>
        {categories.map((category) => (
          <div key={category.id} style={cardStyle()}>
            <div style={{ fontWeight: 800 }}>{category.name}</div>
            <div style={{ marginTop: 10, display: 'grid', gap: 8 }}>
              {category.items.map((item) => (
                <div key={item.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <div>{item.name} — {(item.price_cents / 100).toFixed(2)}€</div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button style={btn('ghost')} onClick={() => patchItem(item, { is_available: !item.is_available })}>
                      dispo: {item.is_available ? 'ON' : 'OFF'}
                    </button>
                    <button style={btn('ghost')} onClick={() => patchItem(item, { is_active: !item.is_active })}>
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
              <button style={btn()} onClick={() => createItem(category.id)}>Ajouter</button>
            </div>
          </div>
        ))}
      </div>
    </Layout>
  )
}
