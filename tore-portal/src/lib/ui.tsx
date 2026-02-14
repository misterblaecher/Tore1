import React from 'react'

export function PageShell({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="tore-shell">
      <header style={{ marginBottom: 16 }}>
        <h1 style={{ margin: 0, fontSize: 26 }}>{title}</h1>
        {subtitle ? <p style={{ margin: '6px 0 0', opacity: 0.8 }}>{subtitle}</p> : null}
      </header>
      {children}
    </div>
  )
}

export function Card({ children }: { children: React.ReactNode }) {
  return <section className="tore-card">{children}</section>
}

export function Badge({ label, tone = 'neutral' }: { label: string; tone?: 'neutral' | 'event' | 'global' | 'bar' | 'success' | 'warning' | 'danger' }) {
  return <span className={`tore-badge tore-badge--${tone}`}>{label}</span>
}

export function Button({ variant = 'primary', ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' }) {
  return <button {...props} className={`tore-btn tore-btn--${variant}`} />
}

export function InlineAlert({ tone = 'warning', children }: { tone?: 'warning' | 'error' | 'success'; children: React.ReactNode }) {
  return <div className={`tore-alert tore-alert--${tone}`}>{children}</div>
}

export function EmptyState({ title, body }: { title: string; body?: string }) {
  return (
    <div className="tore-empty">
      <strong>{title}</strong>
      {body ? <p style={{ margin: '6px 0 0' }}>{body}</p> : null}
    </div>
  )
}

export function Skeleton({ height = 14 }: { height?: number }) {
  return <div className="tore-skeleton" style={{ height }} aria-hidden />
}

export function CursorPager({ nextCursor, onNext }: { nextCursor?: string | null; onNext: () => void }) {
  return (
    <div style={{ marginTop: 12 }}>
      <Button variant="secondary" onClick={onNext} disabled={!nextCursor}>Charger plus</Button>
    </div>
  )
}
