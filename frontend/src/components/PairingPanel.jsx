import { useEffect, useState } from 'react'
import QRCode from 'qrcode'

export default function PairingPanel() {
  const base = import.meta.env.VITE_EDGE_CONTROL_URL || 'http://127.0.0.1:8000'
  const [pairing, setPairing] = useState(null)
  const [qr, setQr] = useState('')
  const [error, setError] = useState('')

  const generate = async () => {
    setError('')
    try {
      const response = await fetch(`${base}/pair/session`, { method: 'POST' })
      const value = await response.json()
      if (!response.ok) throw new Error('Unable to create a pairing code.')
      setPairing(value); setQr(await QRCode.toDataURL(value.pair_url, { errorCorrectionLevel: 'H', margin: 3, width: 300, color: { dark: '#29322f', light: '#f3efe7' } }))
    } catch { setError('The local edge device is unavailable.') }
  }

  useEffect(() => {
    if (!pairing) return undefined
    const timer = setInterval(async () => {
      try { const response = await fetch(`${base}/pair-status/${pairing.session_id}`); const value = await response.json(); setPairing(value); if (value.status === 'expired') setQr('') } catch { /* local device may reconnect */ }
    }, 2000)
    return () => clearInterval(timer)
  }, [base, pairing?.session_id])

  const expires = pairing ? Math.max(0, Math.ceil((new Date(pairing.expires_at) - Date.now()) / 1000)) : 0
  const disconnect = async () => { if (pairing) await fetch(`${base}/pair-status/${pairing.session_id}/disconnect`, { method: 'POST' }).catch(() => {}); setPairing(null); setQr('') }
  return <div className="pairing-panel"><div className="pairing-heading"><div><p className="eyebrow">Phone camera</p><h3>Connect a device</h3></div>{pairing?.status === 'connected' && <span className="input-status">● phone connected</span>}</div>
    {pairing?.status === 'connected' ? <div className="pairing-connected"><strong>PHONE CAMERA</strong><span>Wi-Fi · local network</span><span>WebRTC signaling boundary ready; media transport requires the configured edge adapter.</span><button type="button" onClick={disconnect}>Disconnect</button></div> : <><p className="input-source-note">Scan this QR code with your phone. Keep both devices on the same Wi-Fi network.</p>{qr ? <div className="qr-wrap"><img src={qr} alt="Short-lived CloudCrowd phone pairing QR code" /><span>Pairing expires in {String(Math.floor(expires / 60)).padStart(2, '0')}:{String(expires % 60).padStart(2, '0')}</span></div> : <button type="button" className="pair-button" onClick={generate}>Generate QR</button>}{pairing?.status === 'expired' && <p className="pairing-error">QR expired. Generate a new code.</p>}{error && <p className="pairing-error">{error}</p>}{qr && <button type="button" className="pair-button secondary" onClick={generate}>New QR code</button>}</>}
  </div>
}
