function formatTime(date) {
  if (!date) return '--:--:--'
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function SystemStatus({ connectionStatus, apiError, lastUpdated, onRetry }) {
  const connectionState = connectionStatus
  const connectionLabel = {
    connected: 'Connected', stale: 'Stale', connecting: 'Connecting', disconnected: 'Disconnected',
  }[connectionStatus]

  return (
    <section className="system-section" aria-label="System status">
      <div className="section-heading">
        <h2>System Status</h2>
      </div>
      <div className="card system-card">
        <div className="system-rows">
          <div className="system-row">
            <span className="system-label">API Connection</span>
            <span className={`system-value connection-${connectionState}`}>
              <span className="status-dot-sm" />
              {connectionLabel}
            </span>
          </div>
          <div className="system-row">
            <span className="system-label">Last Successful Update</span>
            <span className="system-value">{formatTime(lastUpdated)}</span>
          </div>
          <div className="system-row">
            <span className="system-label">Refresh Interval</span>
            <span className="system-value">5 seconds</span>
          </div>
        </div>

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
