function formatTime(date) {
  if (!date || Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }).toUpperCase()
}

export default function Header({ currentTime, lastTelemetryAt, telemetryStatus, page, onNavigate }) {
  const statusLabel = { live: 'Live telemetry', stale: 'Stale telemetry', disconnected: 'Telemetry disconnected' }[telemetryStatus]
  const navItems = [
    { id: 'overview', label: 'Overview' },
    { id: 'sources', label: 'Input Sources' },
    { id: 'about', label: 'About' },
  ]

  return (
    <header className="dashboard-header masthead">
      <div className="header-brand">
        <span className="brand-mark" aria-hidden="true">CC</span>
        <div>
          <span className="brand-name">CloudCrowd Analytics</span>
          <span className="brand-sub">Live room intelligence</span>
        </div>
      </div>

      <nav className="main-navigation" aria-label="Primary navigation">
        {navItems.map((item) => (
          <button
            key={item.id}
            type="button"
            className={page === item.id ? 'nav-link nav-link-active' : 'nav-link'}
            onClick={() => onNavigate(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div className={`masthead-status ${telemetryStatus}`}>
        <span>{telemetryStatus === 'live' ? 'System connected' : telemetryStatus === 'stale' ? 'System recovering' : telemetryStatus === 'disconnected' ? 'System disconnected' : 'System waiting'}</span>
        <small>Current time {formatTime(currentTime)}</small>
        <small>Last telemetry {formatTime(lastTelemetryAt)}</small>
      </div>
    </header>
  )
}
