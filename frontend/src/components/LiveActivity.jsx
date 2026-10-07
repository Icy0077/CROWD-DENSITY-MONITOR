function formatTime(date) {
  if (!date || Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function flowInsight(inCount, outCount) {
  if (!Number.isFinite(inCount) || !Number.isFinite(outCount)) return null
  if (inCount > outCount) return 'More people entered during the latest interval.'
  if (outCount > inCount) return 'More people left during the latest interval.'
  return 'Movement was balanced during the latest interval.'
}

export default function LiveActivity({ telemetry, activityLog }) {
  const latest = telemetry[0]
  const insight = latest ? flowInsight(Number(latest.inflow), Number(latest.outflow)) : null

  return (
    <section className="activity-section activity-report" aria-label="Live activity">
      <header className="report-heading compact-heading">
        <div>
          <p className="report-kicker">Crowd activity</p>
          <h2>Movement from this session</h2>
        </div>
        {insight && <p className="report-dek">{insight}</p>}
      </header>

      {!activityLog?.length ? (
        <div className="empty-state report-empty">Real activity will appear as telemetry reaches the dashboard.</div>
      ) : (
        <ol className="activity-timeline">
          {activityLog.map((entry, index) => (
            <li className="activity-row" key={`${entry.timestamp}-${index}`}>
              <time dateTime={entry.timestamp}>{formatTime(new Date(entry.timestamp))}</time>
              <i className={`timeline-marker status-${entry.status}`} aria-hidden="true" />
              <div>
                <strong>{entry.utilization}% occupancy</strong>
                <span><b>+{entry.inflow}</b> in · <b>−{entry.outflow}</b> out</span>
              </div>
              <em className={`activity-status status-${entry.status}`}>{entry.status || 'unknown'}</em>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
