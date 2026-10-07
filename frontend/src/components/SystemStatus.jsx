function formatTime(date) {
  if (!date) return '--:--:--'
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }).toUpperCase()
}

export default function SystemStatus({ telemetryStatus, apiError, lastTelemetryAt, currentTime, onRetry }) {
  const connectionState = telemetryStatus
  const connectionLabel = {
    live: 'Live', stale: 'Stale', disconnected: 'Disconnected',
  }[telemetryStatus]

  return (
    <section className="system-section" aria-label="System status">
      <div className="section-heading">
        <h2>System Status</h2>
      </div>
      <div className="card system-card">
        <div className="system-rows">
          <div className="system-row">
            <span className="system-label">Telemetry Status</span>
            <span className={`system-value connection-${connectionState}`}>
              <span className="status-dot-sm" />
              {connectionLabel}
            </span>
          </div>
          <div className="system-row">
            <span className="system-label">Current Time</span>
            <span className="system-value">{formatTime(currentTime)}</span>
          </div>
          <div className="system-row">
            <span className="system-label">Last Telemetry</span>
            <span className="system-value">{formatTime(lastTelemetryAt)}</span>
          </div>
          <div className="system-row">
            <span className="system-label">Refresh Interval</span>
            <span className="system-value">5 seconds</span>
          </div>
        </div>

        {telemetryStatus === 'stale' && !apiError && (
          <div className="system-error"><div className="system-error-text"><strong>No new telemetry</strong><p>API is reachable, but telemetry has not updated within the freshness window.</p></div></div>
        )}
        {apiError && (
          <div className="system-error">
            <div className="system-error-text">
              <strong>Connection Error</strong>
              <p>{apiError}</p>
            </div>
            {onRetry && (
              <button className="retry-button" onClick={onRetry}>
                Retry
              </button>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
