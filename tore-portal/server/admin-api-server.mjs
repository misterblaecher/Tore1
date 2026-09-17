import express from 'express'
import { createHash, timingSafeEqual } from 'node:crypto'
import { pathToFileURL } from 'node:url'

function equalSecret(left, right) {
  const digest = (value) => createHash('sha256').update(value).digest()
  return timingSafeEqual(digest(left), digest(right))
}

export function createAdminApp(env = process.env, upstreamFetch = fetch) {
  const apiBase = (env.API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '')
  const adminKey = (env.ADMIN_API_KEY || '').trim()
  const basicUser = env.ADMIN_BASIC_USER || ''
  const basicPass = env.ADMIN_BASIC_PASS || ''
  if (!adminKey || !basicUser || !basicPass) {
    throw new Error('Admin proxy disabled: ADMIN_API_KEY, ADMIN_BASIC_USER and ADMIN_BASIC_PASS are required')
  }
  if (basicUser.includes(':')) throw new Error('ADMIN_BASIC_USER cannot contain a colon')
  const upstream = new URL(apiBase)
  const production = env.NODE_ENV === 'production' || /^(prod|production)$/i.test(env.TORE_ENV || '')
  if (!['http:', 'https:'].includes(upstream.protocol) || upstream.username || upstream.password || upstream.search || upstream.hash) {
    throw new Error('API_BASE_URL must be an HTTP(S) URL without credentials, query or fragment')
  }
  if (production && upstream.protocol !== 'https:' && !['localhost', '127.0.0.1', '[::1]'].includes(upstream.hostname)) {
    throw new Error('Production admin upstream must use HTTPS')
  }
  const allowedOrigins = new Set((env.ADMIN_ALLOWED_ORIGINS || '').split(',').map((value) => value.trim()).filter(Boolean))
  const app = express()
  app.disable('x-powered-by')
  app.use('/admin-api', (req, res, next) => {
    res.set('Cache-Control', 'no-store')
    // No permissive CORS: Basic credentials must never authorize cross-site writes.
    const origin = req.get('origin')
    if ((origin && !allowedOrigins.has(origin)) || req.get('sec-fetch-site') === 'cross-site') {
      return res.status(403).json({ error: 'origin_forbidden' })
    }
    const header = req.get('authorization') || ''
    const decoded = /^Basic /i.test(header) ? Buffer.from(header.slice(6), 'base64').toString('utf8') : ''
    const split = decoded.indexOf(':')
    const user = split < 0 ? '' : decoded.slice(0, split)
    const pass = split < 0 ? '' : decoded.slice(split + 1)
    const userMatches = equalSecret(user, basicUser)
    const passMatches = equalSecret(pass, basicPass)
    if (!userMatches || !passMatches) {
      return res.status(401).set('WWW-Authenticate', 'Basic realm="TORE administration", charset="UTF-8"').json({ error: 'unauthorized' })
    }
    next()
  })
  app.use(express.json({ limit: '16kb' }))
  app.all('/admin-api/*', async (req, res) => {
    const path = req.path.replace(/^\/admin-api/, '')
    const collection = /^\/admin\/(account-requests|role-requests)$/.test(path)
    const item = /^\/admin\/(account-requests|role-requests)\/[1-9]\d*$/.test(path)
    if (!(req.method === 'GET' && collection) && !(req.method === 'PATCH' && item)) {
      return res.status(404).json({ error: 'route_not_available' })
    }
    const query = req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : ''
    try {
      const response = await upstreamFetch(`${apiBase}${path}${query}`, {
        method: req.method,
        headers: { 'Content-Type': 'application/json', 'X-Admin-Api-Key': adminKey },
        body: req.method === 'GET' ? undefined : JSON.stringify(req.body || {}),
        signal: AbortSignal.timeout(10_000),
        redirect: 'error',
      })
      res.status(response.status).type('application/json').send(await response.text())
    } catch {
      res.status(502).json({ error: 'admin_upstream_unavailable' })
    }
  })
  app.use((error, _req, res, _next) => {
    const status = error.type === 'entity.too.large' ? 413 : error.type === 'entity.parse.failed' ? 400 : 500
    res.status(status).json({ error: status === 500 ? 'internal_error' : 'invalid_request_body' })
  })
  return app
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const app = createAdminApp()
  // Place behind the portal HTTPS reverse proxy; never expose Basic auth over public HTTP.
  app.listen(Number(process.env.PORT || 8787), process.env.ADMIN_BIND_HOST || '127.0.0.1', () => {
    console.log('TORÈ admin proxy listening')
  })
}
