import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { clearToken } from '../lib/auth'

export default function Layout({ title, children }: { title: string; children: React.ReactNode }) {
  const nav = useNavigate()
  return (
    <div style={{ minHeight: '100vh', background: '#0b0b0f', color: '#fff' }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '16px 20px',
          borderBottom: '1px solid rgba(255,255,255,0.12)',
        }}
      >
        <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
          <Link to="/" style={{ textDecoration: 'none', fontWeight: 800, letterSpacing: 0.4 }}>
            TORÈ
          </Link>
          <span style={{ opacity: 0.8 }}>— {title}</span>
        </div>
        <button
          onClick={() => {
            clearToken()
            nav('/login')
          }}
          style={{
            border: '1px solid rgba(255,255,255,0.18)',
            background: 'transparent',
            color: '#fff',
            padding: '8px 12px',
            borderRadius: 10,
            cursor: 'pointer',
          }}
        >
          Déconnexion
        </button>
      </header>
      <main style={{ padding: 20, maxWidth: 980, margin: '0 auto' }}>{children}</main>
    </div>
  )
}
