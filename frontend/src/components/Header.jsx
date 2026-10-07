function formatTime(date) {
  if (!date || Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }).toUpperCase()
}

export default function Header({ currentTime, lastTelemetryAt, telemetryStatus }) {
  const statusLabel = { live: 'Live telemetry', stale: 'Stale telemetry', disconnected: 'Telemetry disconnected' }[telemetryStatus]

  return (
    <header className="dashboard-header masthead">
      <div className="header-brand">
        <span className="brand-mark" aria-hidden="true">CC</span>
        <div>
          <span className="brand-name">CloudCrowd Analytics</span>
          <span className="brand-sub">A live room report</span>
        </div>
      </div>
      <div className={`masthead-status ${telemetryStatus}`}>
        <span>{statusLabel}</span>
        <small>Current time {formatTime(currentTime)}</small>
        <small>Last telemetry {formatTime(lastTelemetryAt)}</small>
      </div>
    </header>
  )
}
