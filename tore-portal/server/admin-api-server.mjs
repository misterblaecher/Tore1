import express from 'express'
import cors from 'cors'

const app = express()
app.use(cors())
app.use(express.json())

const apiBase = (process.env.API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '')
const adminKey = (process.env.ADMIN_API_KEY || '').trim()
const basicUser = process.env.ADMIN_BASIC_USER || ''
const basicPass = process.env.ADMIN_BASIC_PASS || ''

app.use((req, res, next) => {
  if (!basicUser || !basicPass) return next()
  const hdr = req.headers.authorization || ''
  if (!hdr.startsWith('Basic ')) return res.status(401).set('WWW-Authenticate', 'Basic').json({ error: 'unauthorized' })
  const plain = Buffer.from(hdr.slice(6), 'base64').toString('utf8')
  const [u, p] = plain.split(':')
  if (u !== basicUser || p !== basicPass) return res.status(401).set('WWW-Authenticate', 'Basic').json({ error: 'unauthorized' })
  next()
})

app.all('/admin-api/*', async (req, res) => {
  const path = req.path.replace(/^\/admin-api/, '')
  const target = `${apiBase}${path}${req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : ''}`
  const headers = { 'Content-Type': 'application/json' }
  if (adminKey) headers['X-Admin-Api-Key'] = adminKey
  const upstream = await fetch(target, {
    method: req.method,
    headers,
    body: ['GET', 'HEAD'].includes(req.method) ? undefined : JSON.stringify(req.body || {}),
  })
  const text = await upstream.text()
  res.status(upstream.status).type('application/json').send(text)
})

app.listen(process.env.PORT || 8787, () => {
  console.log('admin api server up')
})
