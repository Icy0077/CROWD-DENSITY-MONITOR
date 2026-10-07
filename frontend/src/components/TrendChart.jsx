export default function TrendChart({ points, labels }) {
  const visibleLabels = labels.length > 2
    ? [labels[0], labels[Math.floor((labels.length - 1) / 2)], labels[labels.length - 1]]
    : labels

  if (points.length < 2) {
    return (
      <section className="trend-section" aria-label="Occupancy trend">
        <div className="section-heading">
        <h2>Session Trend</h2>
          <span className="trend-session-label">Real readings from this session</span>
        </div>
        <div className="card trend-card">
          <div className="empty-state">
            <p className="empty-title">Not enough data for a trend</p>
            <p className="empty-detail">
              The chart will appear after at least two telemetry readings are received.
            </p>
          </div>
        </div>
      </section>
    )
  }

  const width = 700
  const height = 200
  const paddingTop = 20
  const paddingBottom = 10
  const chartHeight = height - paddingTop - paddingBottom

  const maxVal = Math.max(...points, 100)
  const minVal = Math.min(...points, 0)
  const range = maxVal - minVal || 1

  function scaleY(val) {
    return paddingTop + chartHeight - ((val - minVal) / range) * chartHeight
  }

  function scaleX(i) {
    return (i / (points.length - 1)) * width
  }

  const lineCoords = points
    .map((val, i) => `${scaleX(i)},${scaleY(val)}`)
    .join(' ')

  const areaCoords = `0,${height - paddingBottom} ${lineCoords} ${width},${height - paddingBottom}`

  // grid lines at 25%, 50%, 75%, 100%
  const gridValues = [0, 25, 50, 75, 100].filter(v => v >= minVal && v <= maxVal)

  return (
    <section className="trend-section" aria-label="Occupancy trend">
      <div className="section-heading">
        <h2>Session Trend</h2>
        <span className="trend-session-label">Real readings from this session</span>
      </div>

      <div className="card trend-card">
        <div className="trend-summary">
          <strong>{points[points.length - 1]}%</strong>
          <span>current occupancy</span>
        </div>

        <div className="trend-chart-wrap">
          <svg
            viewBox={`0 0 ${width} ${height}`}
            role="img"
            aria-label="Occupancy trend chart for current session"
            className="trend-svg"
          >
            <defs>
              <linearGradient id="trendFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0.12" />
                <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0" />
              </linearGradient>
            </defs>

            {gridValues.map(val => (
              <line
                key={val}
                x1={0}
                x2={width}
                y1={scaleY(val)}
                y2={scaleY(val)}
                className="trend-grid-line"
              />
            ))}

            <polygon points={areaCoords} fill="url(#trendFill)" />
            <polyline points={lineCoords} className="trend-line" />

            {points.map((val, i) => (
              <circle
                key={`${val}-${i}`}
                cx={scaleX(i)}
                cy={scaleY(val)}
                r="3.5"
                className="trend-point"
              />
            ))}
          </svg>

          {labels.length > 0 && (
            <div className="trend-labels">
              {visibleLabels.map((label, i) => (
                <span key={`${label}-${i}`}>{label}</span>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
