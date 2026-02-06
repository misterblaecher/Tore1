import React from 'react'

/* ======================
   STYLES EXPORTÉS
   ====================== */

export function cardStyle(): React.CSSProperties {
  return {
    border: '1px solid rgba(255,255,255,0.12)',
    background: 'rgba(255,255,255,0.04)',
    borderRadius: 16,
    padding: 16,
  }
}

export function inputStyle(): React.CSSProperties {
  return {
    width: '100%',
    borderRadius: 12,
    border: '1px solid rgba(255,255,255,0.18)',
    background: 'rgba(0,0,0,0.35)',
    color: '#fff',
    padding: '10px 12px',
    outline: 'none',
  }
}

export function btn(variant: 'primary' | 'ghost' = 'primary'): React.CSSProperties {
  const base: React.CSSProperties = {
    borderRadius: 12,
    padding: '10px 14px',
    cursor: 'pointer',
    fontWeight: 700,
  }

  if (variant === 'ghost') {
    return {
      ...base,
      border: '1px solid rgba(255,255,255,0.25)',
      background: 'transparent',
      color: '#fff',
    }
  }

  return {
    ...base,
    border: '1px solid rgba(255,0,160,0.4)',
    background: 'rgba(255,0,160,0.25)',
    color: '#fff',
  }
}

/* ======================
   LAYOUT
   ====================== */

export default function Layout({
  title,
  children,
}: {
  title?: string
  children: React.ReactNode
}) {
  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#0b0b0f',
        color: '#fff',
        padding: 24,
        boxSizing: 'border-box',
        fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont',
      }}
    >
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        {title && (
          <h1
            style={{
              marginBottom: 20,
              fontSize: 26,
              fontWeight: 800,
            }}
          >
            {title}
          </h1>
        )}

        {children}
      </div>
    </div>
  )
}

