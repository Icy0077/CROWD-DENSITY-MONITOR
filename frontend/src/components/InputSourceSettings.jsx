import { useEffect, useState } from 'react'
import PairingPanel from './PairingPanel'

const choices = [
  ['webcam', 'Webcam', 'local'], ['usb', 'USB Camera', 'USB'],
  ['wifi', 'Wi-Fi Camera', 'Wi-Fi'], ['rtsp', 'CCTV / RTSP', 'network'],
  ['phone', 'Phone', 'Wi-Fi / WebRTC'], ['bluetooth', 'Bluetooth', 'Bluetooth'], ['file', 'Local Video File', 'local'],
]

export default function InputSourceSettings() {
  const [selected, setSelected] = useState('webcam')
  const [source, setSource] = useState('0')
  const [status, setStatus] = useState('connecting'); const [devices, setDevices] = useState([]); const [message, setMessage] = useState('')
  const base = import.meta.env.VITE_EDGE_CONTROL_URL || 'http://127.0.0.1:8000'

  useEffect(() => {
    fetch(`${base}/input/status`).then(r => r.json()).then(value => {
      setSelected(value.type || 'webcam'); setSource(value.source || (value.type === 'webcam' ? '0' : '')); setStatus(value.connected ? 'connected' : 'disconnected')
    }).catch(() => setStatus('unavailable'))
    fetch(`${base}/input/devices`).then(r => r.json()).then(value => setDevices(value.local_cameras || [])).catch(() => {})
  }, [base])

  const select = async (event) => {
    const input_type = event.target.value
    setSelected(input_type)
    try {
      const response = await fetch(`${base}/input/select`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ input_type, source: source || undefined }) })
      const value = await response.json().catch(() => ({})); setStatus(response.ok ? 'selected' : 'error'); setMessage(value.message || '')
    } catch { setStatus('edge offline'); setMessage('The local edge device is unavailable.') }
  }

  return <section className="card input-source-card" aria-labelledby="input-source-title">
    <div className="section-heading"><div><p className="eyebrow">Local edge control</p><h2 id="input-source-title" className="section-title">Input Source</h2></div><span className="input-status">● {status}</span></div>
    <label className="input-source-label" htmlFor="input-source-select">Device</label>
    <select id="input-source-select" value={selected} onChange={select}>{choices.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
    <label className="input-source-label" htmlFor="input-source-value">Source address, index, or file path</label>
    <input id="input-source-value" className="input-source-value" value={source} onChange={event => setSource(event.target.value)} onBlur={() => select({ target: { value: selected } })} placeholder="0, rtsp://..., or video.mp4" />
    {selected === 'webcam' || selected === 'usb' ? <p className="input-source-note">Detected local cameras: {devices.length ? devices.map(device => device.label).join(', ') : 'none reported'}</p> : null}
    {selected === 'bluetooth' ? <p className="input-source-note">Bluetooth supports discovery, pairing, and control metadata. It does not imply a video stream.</p> : null}
    {message ? <p className="input-source-note">{message}</p> : null}
    <p className="input-source-note">The edge device connects locally. Raw video never travels through AWS.</p>
    {selected === 'phone' ? <PairingPanel /> : null}
  </section>
}
