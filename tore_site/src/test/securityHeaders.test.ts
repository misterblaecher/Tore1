import { readFileSync } from 'node:fs'
import { describe, expect, test } from 'vitest'

describe('deployment security headers', () => {
  const config = JSON.parse(readFileSync('vercel.json', 'utf8'))
  const values = Object.fromEntries(config.headers[0].headers.map((header: { key: string; value: string }) => [header.key, header.value]))

  test('defines CSP and clickjacking protections', () => {
    expect(values['Content-Security-Policy']).toContain("frame-ancestors 'none'")
    expect(values['Content-Security-Policy']).toContain("object-src 'none'")
    expect(values['Content-Security-Policy']).not.toContain("'unsafe-eval'")
    expect(values['X-Frame-Options']).toBe('DENY')
  })

  test('defines transport and browser hardening headers', () => {
    expect(values['X-Content-Type-Options']).toBe('nosniff')
    expect(values['Strict-Transport-Security']).toBe('max-age=31536000')
    expect(values['Referrer-Policy']).toBe('strict-origin-when-cross-origin')
    expect(values['Permissions-Policy']).toContain('camera=()')
  })
})
