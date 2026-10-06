function formatTime(date) {
  if (!date || Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function Header({ connectionStatus, lastUpdated }) {
  const statusLabel = {
    connected: 'Connected', stale: 'Stale', connecting: 'Connecting', disconnected: 'Disconnected',
  }[connectionStatus]

  return (
    <header className="dashboard-header masthead">
      <div className="header-brand">
        <span className="brand-mark" aria-hidden="true">CC</span>
        <div>
          <span className="brand-name">CloudCrowd Analytics</span>
          <span className="brand-sub">A live room report</span>
        </div>
      </div>
      <div className={`masthead-status ${connectionStatus}`}>
        <span>{statusLabel}</span>
        <small>Telemetry timestamp {formatTime(lastUpdated)}</small>
      </div>
    </header>
  )
}
