import { readFileSync } from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

test('portal deployment config defines security headers', () => {
  const config = JSON.parse(readFileSync(new URL('../vercel.json', import.meta.url), 'utf8'))
  const values = Object.fromEntries(config.headers[0].headers.map((header) => [header.key, header.value]))
  assert.match(values['Content-Security-Policy'], /frame-ancestors 'none'/)
  assert.doesNotMatch(values['Content-Security-Policy'], /unsafe-eval/)
  assert.equal(values['X-Content-Type-Options'], 'nosniff')
  assert.equal(values['X-Frame-Options'], 'DENY')
  assert.equal(values['Strict-Transport-Security'], 'max-age=31536000')
})
