import React from 'react'
import { API_BASE } from '../lib/api'

export default function ApiUnavailable() {
  return (
    <div
      style={{
        border: '1px solid rgba(255,255,255,0.12)',
        borderRadius: 16,
        padding: 20,
        background: 'rgba(255,255,255,0.04)',
        display: 'grid',
        gap: 10,
      }}
    >
      <div style={{ fontSize: 22, fontWeight: 800 }}>API indisponible</div>
      <div style={{ opacity: 0.85 }}>
        Impossible de joindre le serveur. Vérifie la connexion réseau ou la variable <code>VITE_API_BASE_URL</code>.
      </div>
      <div style={{ opacity: 0.7, fontSize: 13 }}>API: {API_BASE}</div>
      <button
        type="button"
        onClick={() => window.location.reload()}
        style={{
          padding: '10px 12px',
          borderRadius: 12,
          border: '1px solid rgba(255,255,255,0.18)',
          background: '#ffffff',
          color: '#000',
          fontWeight: 800,
          cursor: 'pointer',
          width: 'fit-content',
        }}
      >
        Réessayer
      </button>
    </div>
  )
}
