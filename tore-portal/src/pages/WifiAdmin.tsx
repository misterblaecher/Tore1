import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout, { btn, cardStyle, inputStyle } from '../ui/Layout'
import { api } from '../lib/api'

export default function WifiAdmin() {
  const { eventId } = useParams()
  const [barId, setBarId] = useState('')
  const [ssid, setSsid] = useState('')
  const [password, setPassword] = useState('')
  const [note, setNote] = useState('')
  const [preview, setPreview] = useState<any>(null)

  useEffect(() => {
    ;(async () => {
      const bar = await api<any>('/partner/portal/bar')
      setBarId(String(bar.id))
    })()
  }, [])

  const refreshPreview = async () => {
    if (!barId || !eventId) return
    try {
      setPreview(await api<any>(`/public/wifi?bar_id=${barId}&event_id=${eventId}`))
    } catch {
      setPreview({ status: 'not available (204 or gated)' })
    }
  }

  return <Layout title="Wifi Admin"><div style={cardStyle()}>
    <div>Event: {eventId}</div>
    <input style={inputStyle()} placeholder="SSID" value={ssid} onChange={(e) => setSsid(e.target.value)} />
    <input style={{ ...inputStyle(), marginTop: 8 }} placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
    <input style={{ ...inputStyle(), marginTop: 8 }} placeholder="Note" value={note} onChange={(e) => setNote(e.target.value)} />
    <button style={{ ...btn(), marginTop: 8 }} onClick={async () => {
      await api('/partner/portal/wifi/set', { method: 'POST', body: JSON.stringify({ bar_id: Number(barId), event_id: Number(eventId), ssid, password, note }) })
      await refreshPreview()
    }}>Save</button>
    <button style={{ ...btn('ghost'), marginTop: 8, marginLeft: 8 }} onClick={refreshPreview}>Preview /public/wifi</button>
    <pre>{JSON.stringify(preview, null, 2)}</pre>
  </div></Layout>
}