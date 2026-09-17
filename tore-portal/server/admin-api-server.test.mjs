import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createAdminApp } from './admin-api-server.mjs'

const env = {
  API_BASE_URL: 'https://api.example.test',
  ADMIN_API_KEY: 'test-server-key',
  ADMIN_BASIC_USER: 'reviewer',
  ADMIN_BASIC_PASS: 'test:password',
  ADMIN_ALLOWED_ORIGINS: 'https://portal.example.test',
}
const authorization = `Basic ${Buffer.from('reviewer:test:password').toString('base64')}`

async function serve(t, upstream) {
  const server = createAdminApp(env, upstream).listen(0, '127.0.0.1')
  await new Promise((resolve) => server.once('listening', resolve))
  t.after(() => new Promise((resolve) => { server.close(resolve); server.closeAllConnections() }))
  return `http://127.0.0.1:${server.address().port}`
}

test('missing credentials disable the proxy, including partial Basic configuration', () => {
  for (const name of ['ADMIN_API_KEY', 'ADMIN_BASIC_USER', 'ADMIN_BASIC_PASS']) {
    assert.throws(() => createAdminApp({ ...env, [name]: '' }), /disabled/)
  }
})
test('production refuses an insecure upstream and credentials in its URL', () => {
  assert.throws(() => createAdminApp({ ...env, NODE_ENV: 'production', API_BASE_URL: 'http://api.example.test' }), /HTTPS/)
  assert.throws(() => createAdminApp({ ...env, API_BASE_URL: 'https://user:secret@api.example.test' }), /without credentials/)
})
test('unauthenticated and wrong-password requests never reach the backend', async (t) => {
  const base = await serve(t, () => { assert.fail('unauthorized upstream call') })
  for (const header of ['', 'Basic ' + Buffer.from('reviewer:wrong').toString('base64'), 'Bearer forged']) {
    const response = await fetch(`${base}/admin-api/admin/role-requests`, { headers: { authorization: header } })
    assert.equal(response.status, 401)
    assert.match(response.headers.get('www-authenticate'), /^Basic /)
    assert.equal(response.headers.get('cache-control'), 'no-store')
  }
})
test('authenticated review forwards only server credentials and preserves query/status', async (t) => {
  const base = await serve(t, async (url, options) => {
    assert.equal(url, 'https://api.example.test/admin/role-requests?status=pending&limit=100')
    assert.equal(options.headers['X-Admin-Api-Key'], env.ADMIN_API_KEY)
    assert.equal(options.headers.Authorization, undefined)
    assert.equal(options.redirect, 'error')
    assert.ok(options.signal)
    return new Response(JSON.stringify({ items: [] }), { status: 200 })
  })
  const response = await fetch(`${base}/admin-api/admin/role-requests?status=pending&limit=100`, { headers: { authorization } })
  assert.equal(response.status, 200)
  assert.deepEqual(await response.json(), { items: [] })
})
test('arbitrary routes and methods cannot borrow the administrator key', async (t) => {
  const base = await serve(t, () => { assert.fail('unexpected upstream') })
  for (const [path, method] of [['/admin/users', 'GET'], ['/admin/role-requests', 'POST'], ['/admin/role-requests/1', 'DELETE'], ['/admin/role-requests/1/extra', 'PATCH']]) {
    assert.equal((await fetch(`${base}/admin-api${path}`, { method, headers: { authorization } })).status, 404)
  }
})
test('cross-origin Basic-auth writes are rejected without forwarding', async (t) => {
  const base = await serve(t, () => { assert.fail('cross-site upstream call') })
  const response = await fetch(`${base}/admin-api/admin/role-requests/1`, { method: 'PATCH', headers: { authorization, Origin: 'https://attacker.test' } })
  assert.equal(response.status, 403)
  assert.equal(response.headers.get('access-control-allow-origin'), null)
})
test('same-origin review PATCH preserves the body and upstream rejection', async (t) => {
  const base = await serve(t, async (_url, options) => {
    assert.deepEqual(JSON.parse(options.body), { action: 'approve' })
    return new Response(JSON.stringify({ detail: 'already_reviewed' }), { status: 409 })
  })
  const response = await fetch(`${base}/admin-api/admin/role-requests/12`, { method: 'PATCH', headers: { authorization, Origin: env.ADMIN_ALLOWED_ORIGINS, 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'approve' }) })
  assert.equal(response.status, 409)
})
test('upstream outage returns a stable error without leaking credentials', async (t) => {
  const base = await serve(t, async () => { throw new Error(env.ADMIN_API_KEY) })
  const response = await fetch(`${base}/admin-api/admin/account-requests`, { headers: { authorization } })
  assert.equal(response.status, 502)
  assert.deepEqual(await response.json(), { error: 'admin_upstream_unavailable' })
})
test('oversized bodies are refused before forwarding', async (t) => {
  const base = await serve(t, () => { assert.fail('oversized upstream call') })
  const response = await fetch(`${base}/admin-api/admin/role-requests/1`, { method: 'PATCH', headers: { authorization, 'Content-Type': 'application/json' }, body: JSON.stringify({ note: 'x'.repeat(20_000) }) })
  assert.equal(response.status, 413)
})
