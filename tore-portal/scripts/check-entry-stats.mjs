const apiBase = process.env.API_BASE || process.env.VITE_API_BASE_URL || 'http://localhost:8000'
const eventId = process.env.EVENT_ID
const token = process.env.PARTNER_TOKEN

if (!eventId || !token) {
  console.error('Usage: EVENT_ID=123 PARTNER_TOKEN=... node scripts/check-entry-stats.mjs')
  process.exit(1)
}

const url = `${apiBase}/events/${eventId}/entry/stats`

try {
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  })
  const text = await res.text()
  console.log(`[${res.status}] ${url}`)
  console.log(text)
  if (!res.ok) process.exit(2)
} catch (err) {
  console.error('Request failed', err)
  process.exit(3)
}
