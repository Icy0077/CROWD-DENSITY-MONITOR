function formatTime(date) {
  if (!date) return '--:--:--'
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }).toUpperCase()
}

export default function SystemStatus({ telemetryStatus, apiError, lastTelemetryAt, currentTime, onRetry }) {
  const connectionState = telemetryStatus
  const apiLabel = apiError ? 'Disconnected' : 'Healthy'
  const connectionLabel = {
    live: 'Live', stale: 'Stale', disconnected: 'Disconnected',
  }[telemetryStatus]

  const isRecovering = telemetryStatus === 'live'
  const staleSummary = telemetryStatus === 'stale' && !apiError
    ? 'Telemetry is stale. Values below are last known and should not be treated as current.'
    : null

  return (
    <section className="system-section" aria-label="System status">
      <div className="section-heading">
        <h2>Cloud Status</h2>
      </div>
      <div className="card system-card">
        <div className="system-rows">
          <div className="system-row">
            <span className="system-label">Cloud telemetry</span>
            <span className={`system-value connection-${connectionState}`}>
              <span className="status-dot-sm" />
              {connectionLabel}
            </span>
          </div>
          <div className="system-row">
            <span className="system-label">API status</span>
            <span className="system-value">{apiLabel}</span>
          </div>
          <div className="system-row">
            <span className="system-label">Last telemetry</span>
            <span className="system-value">{formatTime(lastTelemetryAt)}</span>
          </div>
          <div className="system-row">
            <span className="system-label">Refresh interval</span>
            <span className="system-value">5 seconds</span>
          </div>
        </div>

        {staleSummary && (
          <div className="system-error"><div className="system-error-text"><strong>Telemetry stale</strong><p>{staleSummary}</p></div></div>
        )}
        {isRecovering && (
          <div className="system-error success-state"><div className="system-error-text"><strong>Telemetry recovered</strong><p>Fresh readings are updating normally again.</p></div></div>
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
