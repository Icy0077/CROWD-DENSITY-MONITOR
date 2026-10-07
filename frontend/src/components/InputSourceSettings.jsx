import { useEffect, useState } from 'react'
import PairingPanel from './PairingPanel'

const choices = [
  ['webcam', 'Webcam'], ['usb', 'USB Camera'], ['wifi', 'Wi-Fi Camera'], ['rtsp', 'CCTV / RTSP'],
  ['phone', 'Phone'], ['bluetooth', 'Bluetooth — control/discovery only'], ['file', 'Local Video File'],
]

function sourceHint(type) {
  if (type === 'wifi') return 'RTSP or HTTP camera URL'
  if (type === 'rtsp') return 'RTSP camera URL'
  if (type === 'file') return 'Local .mp4, .avi, .mov, .mkv, .webm, or .mjpeg path'
  return ''
}

export default function InputSourceSettings() {
  const [selected, setSelected] = useState('webcam')
  const [source, setSource] = useState('0')
  const [cameraChoice, setCameraChoice] = useState(null)
  const [status, setStatus] = useState('CONNECTING'); const [devices, setDevices] = useState([]); const [message, setMessage] = useState('')
  const base = import.meta.env.VITE_EDGE_CONTROL_URL || 'http://127.0.0.1:8000'

  const applyStatus = (value, syncSource = true) => {
    if (syncSource) {
      setSelected(value.type || 'webcam')
      setSource(value.source || (value.type === 'webcam' ? '0' : ''))
      if (value.source !== undefined && value.source !== null) setCameraChoice(String(value.source))
    }
    setStatus(value.state || (value.connected ? 'CONNECTED' : 'AVAILABLE'))
    setMessage(value.message || '')
  }

  const cameraSource = (type) => {
    const cameras = devices.slice().sort((a, b) => Number(a.index) - Number(b.index))
    if (type === 'webcam') return cameras[0]?.index ?? null
    return cameras.find(camera => Number(camera.index) !== Number(cameras[0]?.index))?.index ?? null
  }

  useEffect(() => {
    fetch(`${base}/input/status`).then(r => r.json()).then(applyStatus).catch(() => setStatus('UNAVAILABLE'))
    fetch(`${base}/input/devices`).then(r => r.json()).then(value => setDevices(value.local_cameras || [])).catch(() => {})
    const timer = setInterval(() => fetch(`${base}/input/status`).then(r => r.json()).then(value => applyStatus(value, false)).catch(() => setStatus('UNAVAILABLE')), 2000)
    return () => clearInterval(timer)
  }, [base])

  const select = async (event, commit = true, sourceOverride = undefined) => {
    const inputType = event.target.value
    if (inputType === 'bluetooth') {
      setSelected('bluetooth'); setStatus('UNSUPPORTED'); setMessage('Bluetooth video streaming is not supported. Use USB, Wi-Fi/RTSP, CCTV/RTSP, or Phone.')
      return
    }
    if (inputType === 'phone') {
      setSelected('phone'); setStatus('UNSUPPORTED'); setMessage('Phone pairing is available, but WebRTC frame reception is not implemented in this edge build.')
      return
    }
    if (!commit && inputType !== 'webcam' && inputType !== 'usb') {
      setSelected(inputType); setSource(''); setStatus('READY'); setMessage(`Enter the ${sourceHint(inputType).toLowerCase()} below, then press Tab.`); return
    }
    const requestedSource = sourceOverride ?? (inputType === 'webcam' || inputType === 'usb' ? (cameraChoice ?? cameraSource(inputType)) : source)
    if ((inputType === 'webcam' || inputType === 'usb') && requestedSource === null) {
      setStatus('ERROR'); setMessage('No additional local camera was detected. Connect the camera and try again.'); return
    }
    try {
      const response = await fetch(`${base}/input/select`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ input_type: inputType, source: requestedSource ?? undefined }) })
      const value = await response.json().catch(() => ({}))
      if (!response.ok) {
        setStatus('ERROR'); setMessage(value.error || 'Camera source was not changed'); return
      }
      applyStatus(value); setMessage('Camera source switched successfully')
    } catch { setStatus('ERROR'); setMessage('Camera source was not changed: the edge device is unavailable.') }
  }

  return <section className="card input-source-card" aria-labelledby="input-source-title">
    <div className="section-heading"><div><p className="eyebrow">Local edge control</p><h2 id="input-source-title" className="section-title">Input Source</h2></div><span className="input-status">● {status}</span></div>
    <div className="source-pills" role="group" aria-label="Input source"><select id="input-source-select" value={selected} onChange={event => select(event, event.target.value === 'webcam' || event.target.value === 'usb')} aria-label="Input source">{choices.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>{choices.map(([value, label]) => <button type="button" key={value} className={selected === value ? 'source-pill source-pill-active' : 'source-pill'} onClick={() => select({ target: { value } }, value === 'webcam' || value === 'usb')}>{label.replace(' Camera', '')}</button>)}</div>
    {selected === 'webcam' || selected === 'usb' ? <div className="camera-choices"><span className="input-source-label">{selected === 'webcam' ? 'Choose a local camera' : 'Choose a USB camera'}</span>{devices.length ? <div className="camera-choice-list">{devices.map((device, index) => <button type="button" key={`${device.index}-${index}`} className={String(cameraChoice) === String(device.index) ? 'camera-choice camera-choice-active' : 'camera-choice'} onClick={() => { setCameraChoice(String(device.index)); select({ target: { value: selected } }, true, device.index) }}><span className="camera-choice-icon">◉</span><span>{device.label || `Local camera ${index + 1}`}</span></button>)}</div> : <p className="input-source-note">No local cameras detected. Connect a camera and refresh.</p>}</div> : null}
    {selected !== 'phone' && selected !== 'bluetooth' && selected !== 'webcam' && selected !== 'usb' ? <><label className="input-source-label" htmlFor="input-source-value">{sourceHint(selected)}</label><input id="input-source-value" type="text" className="input-source-value" value={source} onChange={event => setSource(event.target.value)} placeholder={selected === 'file' ? 'C:\\video\\crowd.mp4' : 'rtsp://..., or http://...'} /><button type="button" className="source-connect-button" onClick={() => select({ target: { value: selected } })}>Connect source</button></> : null}
    {selected === 'bluetooth' ? <p className="input-source-note">Bluetooth video streaming is not supported. Use USB, Wi-Fi/RTSP, CCTV/RTSP, or Phone.</p> : null}
    {message ? <p className="input-source-note">{message}</p> : null}
    <p className="input-source-note">Pipeline: {status === 'ACTIVE' ? 'ACTIVE · receiving frames' : status}. Raw video never travels through AWS.</p>
    {selected === 'phone' ? <PairingPanel /> : null}
  </section>
}
