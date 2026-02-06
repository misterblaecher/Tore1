import React from 'react'

export function Shell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ padding: 20, maxWidth: 980, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 22, letterSpacing: 0.2 }}>{title}</h1>
      </div>
      <div style={{ marginTop: 16 }}>{children}</div>
    </div>
  )
}

export function Card({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        border: '1px solid rgba(127,127,127,0.25)',
        borderRadius: 14,
        padding: 16,
        background: 'rgba(127,127,127,0.06)',
      }}
    >
      {children}
    </div>
  )
}

export function Row({ children }: { children: React.ReactNode }) {
  return <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>{children}</div>
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'grid', gap: 6, minWidth: 220 }}>
      <span style={{ fontSize: 12, opacity: 0.8 }}>{label}</span>
      {children}
    </label>
  )
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      style={{
        padding: '10px 12px',
        borderRadius: 12,
        border: '1px solid rgba(127,127,127,0.35)',
        background: 'transparent',
        outline: 'none',
      }}
    />
  )
}

export function Button(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      style={{
        padding: '10px 12px',
        borderRadius: 12,
        border: '1px solid rgba(127,127,127,0.35)',
        background: 'rgba(127,127,127,0.14)',
        cursor: props.disabled ? 'not-allowed' : 'pointer',
      }}
    />
  )
}
