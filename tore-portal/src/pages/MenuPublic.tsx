import React, { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout, { cardStyle } from '../ui/Layout'
import { API_BASE } from '../lib/api'

type MenuItem = { id: number; name: string; description: string; price_cents: number }
type MenuCategory = { id: number; name: string; items: MenuItem[] }
type MenuPublic = { bar: { id: number; name: string; city: string }; categories: MenuCategory[] }
type CartLine = { item: MenuItem; qty: number }

export default function MenuPublic() {
  const { barId, itemId } = useParams()
  const [data, setData] = useState<MenuPublic | null>(null)
  const [item, setItem] = useState<MenuItem | null>(null)
  const [cart, setCart] = useState<Record<number, CartLine>>({})
  const [statusMsg, setStatusMsg] = useState<string>('')

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

  const cartLines = useMemo(() => Object.values(cart), [cart])
  const totalCents = useMemo(() => cartLines.reduce((acc, line) => acc + line.item.price_cents * line.qty, 0), [cartLines])

  const addToCart = (menuItem: MenuItem) => {
    setCart((prev) => {
      const existing = prev[menuItem.id]
      return {
        ...prev,
        [menuItem.id]: {
          item: menuItem,
          qty: existing ? existing.qty + 1 : 1,
        },
      }
    })
    if (barId) {
      fetch(`${API_BASE}/menu/track`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bar_id: Number(barId), item_id: menuItem.id, action: 'add' }),
      })
    }
  }

  const submitOrder = async () => {
    if (!barId || cartLines.length === 0) return
    setStatusMsg('')
    const idempotency = `menu-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const res = await fetch(`${API_BASE}/orders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        bar_id: Number(barId),
        device_id: 'web-menu',
        idempotency_key: idempotency,
        items: cartLines.map((line) => ({ item_id: line.item.id, qty: line.qty })),
      }),
    })
    if (!res.ok) {
      setStatusMsg('Erreur commande')
      return
    }
    const payload = await res.json()
    setCart({})
    setStatusMsg(`Commande #${payload.id} envoyée`) 
  }

  return (
    <Layout title={data ? `Menu — ${data.bar.name}` : 'Menu'}>
      {item ? (
        <div style={cardStyle()}>
          <h3>{item.name}</h3>
          <p>{item.description}</p>
          <div>{(item.price_cents / 100).toFixed(2)}€</div>
          <button onClick={() => addToCart(item)} style={{ marginTop: 8 }}>Ajouter au panier</button>
          <div style={{ marginTop: 8 }}>
            <Link to={`/menu/${barId}`}>← Retour menu</Link>
          </div>
        </div>
      ) : null}

      {!item && data?.categories.map((category) => (
        <section key={category.id} style={{ ...cardStyle(), marginBottom: 12 }}>
          <h3>{category.name}</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            {category.items.map((row) => (
              <div key={row.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Link to={`/menu/${barId}/item/${row.id}`} style={{ color: '#fff', textDecoration: 'none' }}>
                  {row.name} — {(row.price_cents / 100).toFixed(2)}€
                </Link>
                <button onClick={() => addToCart(row)}>Ajouter</button>
              </div>
            ))}
          </div>
        </section>
      ))}

      <section style={cardStyle()}>
        <h3>Panier</h3>
        {cartLines.length === 0 ? <div>Panier vide</div> : null}
        {cartLines.map((line) => (
          <div key={line.item.id} style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>{line.item.name} x{line.qty}</span>
            <span>{((line.item.price_cents * line.qty) / 100).toFixed(2)}€</span>
          </div>
        ))}
        <div style={{ marginTop: 8, fontWeight: 700 }}>Total: {(totalCents / 100).toFixed(2)}€</div>
        <button onClick={submitOrder} disabled={cartLines.length === 0} style={{ marginTop: 10 }}>Commander</button>
        {statusMsg ? <div style={{ marginTop: 8 }}>{statusMsg}</div> : null}
      </section>
    </Layout>
  )
}
