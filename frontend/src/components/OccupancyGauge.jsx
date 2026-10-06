function statusMessage(status) {
  if (status === 'green') return 'The room remains comfortably below capacity.'
  if (status === 'yellow') return 'The room is moderately occupied; monitor movement.'
  if (status === 'red') return 'The room is near capacity and needs attention.'
  return 'Waiting for a backend capacity status.'
}

export default function OccupancyGauge({ occupancy, capacity, percentage, status }) {
  const hasData = percentage !== null && percentage !== undefined
  const pct = hasData ? Math.min(100, Math.max(0, percentage)) : 0
  const label = status ? `${status.charAt(0).toUpperCase()}${status.slice(1)}` : 'Unknown'

  return (
    <section className="gauge-section capacity-reading" aria-label="Capacity reading">
      <div className="capacity-intro">
        <p className="report-kicker">Capacity reading</p>
        <h2>How full is the space?</h2>
      </div>
      <div className="capacity-detail">
        <p><strong>{hasData ? `${pct}%` : '—'}</strong> {hasData ? `${occupancy} of ${capacity} people` : 'No data available'}</p>
        <div className="capacity-rule capacity-rule-wide" role="progressbar" aria-valuenow={pct} aria-valuemin="0" aria-valuemax="100">
          <span style={{ width: `${pct}%` }} />
        </div>
        <p className={`capacity-status status-${status || 'unknown'}`}><i />{label}: {statusMessage(status)}</p>
      </div>
    </section>
  )
}
