import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout, { cardStyle } from '../ui/Layout'
import { API_BASE } from '../lib/api'

type MenuItem = { id: number; name: string; description: string; price_cents: number }
type MenuCategory = { id: number; name: string; items: MenuItem[] }
type MenuPublic = { bar: { id: number; name: string; city: string }; categories: MenuCategory[] }

export default function MenuPublic() {
  const { barId, itemId } = useParams()
  const [data, setData] = useState<MenuPublic | null>(null)
  const [item, setItem] = useState<MenuItem | null>(null)

  useEffect(() => {
    if (!barId) return
    fetch(`${API_BASE}/menu/public/${barId}`).then((r) => r.json()).then((payload) => {
      setData(payload)
      fetch(`${API_BASE}/menu/track`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bar_id: Number(barId), action: 'view' }) })
    })
  }, [barId])

  useEffect(() => {
    if (!barId || !itemId) {
      setItem(null)
      return
    }
    fetch(`${API_BASE}/menu/public/${barId}/items/${itemId}`).then((r) => r.json()).then((payload) => {
      setItem(payload)
      fetch(`${API_BASE}/menu/track`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bar_id: Number(barId), item_id: Number(itemId), action: 'click' }) })
    })
  }, [barId, itemId])

  return (
    <Layout title={data ? `Menu — ${data.bar.name}` : 'Menu'}>
      {item ? (
        <div style={cardStyle()}>
          <h3>{item.name}</h3>
          <p>{item.description}</p>
          <div>{(item.price_cents / 100).toFixed(2)}€</div>
          <Link to={`/menu/${barId}`}>← Retour menu</Link>
        </div>
      ) : null}

      {!item && data?.categories.map((category) => (
        <section key={category.id} style={{ ...cardStyle(), marginBottom: 12 }}>
          <h3>{category.name}</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            {category.items.map((row) => (
              <Link key={row.id} to={`/menu/${barId}/item/${row.id}`} style={{ color: '#fff', textDecoration: 'none' }}>
                {row.name} — {(row.price_cents / 100).toFixed(2)}€
              </Link>
            ))}
          </div>
        </section>
      ))}
    </Layout>
  )
}
