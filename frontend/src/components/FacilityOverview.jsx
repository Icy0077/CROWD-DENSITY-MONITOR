import FlowIllustration from './FlowIllustration'

function displayValue(value) {
  return value === null || value === undefined ? '—' : value
}

function statusLabel(status) {
  return status ? `${status.charAt(0).toUpperCase()}${status.slice(1)} conditions` : 'Status unavailable'
}

export default function FacilityOverview({ data }) {
  const { facilityId, occupancy, capacity, utilization, estimatedWaitTime, inflow, outflow, status } = data
  const facilityName = facilityId === 'facility-1' ? 'Facility 1' : facilityId || 'Awaiting live telemetry'
  const percentage = utilization === null || utilization === undefined
    ? null
    : Math.max(0, Math.min(100, utilization))

  return (
    <section className="facility-section editorial-facility" aria-label="Current facility reading">
      <header className="report-heading">
        <div>
          <p className="report-kicker">Facility 01</p>
          <h1>{facilityName}</h1>
        </div>
        <p className="report-dek">A live reading of the room, updated from the camera pipeline.</p>
      </header>

      <div className="facility-report">
        <div className="occupancy-reading">
          <p className="report-label">People currently inside</p>
          <div className="occupancy-number" aria-label={`${displayValue(occupancy)} people inside out of ${displayValue(capacity)} capacity`}>
            <strong>{displayValue(occupancy)}</strong>
            <span>/ {displayValue(capacity)}</span>
          </div>
          <p className="occupancy-caption">
            {percentage === null ? 'Waiting for a live occupancy reading.' : `${percentage}% of available capacity`}
          </p>
          <div className="capacity-rule" aria-label="Capacity usage">
            <span style={{ width: `${percentage ?? 0}%` }} />
          </div>
          <div className="capacity-meta">
            <span>Capacity utilization</span>
            <strong>{percentage === null ? '—' : `${percentage}%`}</strong>
          </div>
          <p className={`status-note status-note-${status || 'unknown'}`}>
            <span className="status-dot-sm" />
            {statusLabel(status)}
          </p>
        </div>

        <figure className="flow-figure">
          <FlowIllustration inflow={inflow} outflow={outflow} />
          <figcaption>
            <span><b>In</b> {displayValue(inflow)}</span>
            <span><b>Out</b> {displayValue(outflow)}</span>
            <small>Observed during the latest reporting interval</small>
          </figcaption>
        </figure>
      </div>

      <div className="reading-notes">
        <p><span>Estimated wait</span><strong>{displayValue(estimatedWaitTime)} min</strong></p>
        <p><span>Latest flow</span><strong>{displayValue(inflow)} in · {displayValue(outflow)} out</strong></p>
      </div>
    </section>
  )
}
