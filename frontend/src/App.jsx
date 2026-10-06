import { useEffect, useState } from 'react'
import { getLatestTelemetry } from './services/api'

const chartPoints = [31, 37, 34, 46, 42, 55, 52, 67, 62, 73, 68, 76]
const chartLabels = ['08:00', '09:00', '10:00', '11:00', '12:00', '13:00']

const initialDashboardData = {
  occupancy: 68,
  capacity: 100,
  occupancyPercentage: 68,
  waitTime: 8,
  inCount: 12,
  outCount: 4,
  status: 'yellow',
  lastUpdated: new Date('2026-09-17T10:42:18Z'),
  chartPoints,
  telemetry: [],
}

function formatStatus(status) {
  return status.charAt(0).toUpperCase() + status.slice(1)
}

function formatTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function StatCard({ label, value, suffix, detail, tone, progress, children }) {
  return (
    <article className={`stat-card ${tone || ''}`}>
      <div className="card-heading">
        <span>{label}</span>
        <span className="card-mark">{children}</span>
      </div>
      <div className="stat-value">
        {value}<small>{suffix}</small>
      </div>
      <p className="stat-detail">{detail}</p>
      {progress && <div className="occupancy-progress" aria-label={`${progress}% occupancy`}><span style={{ width: `${progress}%` }} /></div>}
    </article>
  )
}

function StatusCard({ status }) {
  return (
    <article className="status-card">
      <div className="card-heading">
        <span>Current status</span>
        <span className={`live-dot ${status.toLowerCase()}`}><i /> Live</span>
      </div>
      <div className="status-content">
        <div className={`status-orb ${status.toLowerCase()}`}><span /></div>
        <div>
          <strong>{status}</strong>
          <p>{status === 'Green' ? 'Flow is moving normally' : status === 'Yellow' ? 'Monitor the current flow' : 'Capacity needs attention'}</p>
        </div>
      </div>
      <div className="status-options" aria-label="Status thresholds">
        {['Green', 'Yellow', 'Red'].map((option) => (
          <span className={status === option ? 'selected' : ''} key={option}>
            <span className={`mini-dot ${option.toLowerCase()}`} />{option}
          </span>
        ))}
      </div>
    </article>
  )
}

function OccupancyChart({ points }) {
  const width = 700
  const height = 230
  const chartCoordinates = points.map((value, index) => `${(index / (points.length - 1)) * width},${height - value * 2.2}`).join(' ')
  const areaPoints = `0,${height} ${chartCoordinates} ${width},${height}`

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Occupancy history from 8 AM to 1 PM">
        <defs>
          <linearGradient id="chart-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#d46b48" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#d46b48" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3].map((line) => <line key={line} x1="0" x2={width} y1={line * 55} y2={line * 55} className="grid-line" />)}
        <polygon points={areaPoints} fill="url(#chart-fill)" />
        <polyline points={chartCoordinates} className="chart-line" />
        {points.map((value, index) => <circle key={value + index} cx={(index / (points.length - 1)) * width} cy={height - value * 2.2} r="4" className="chart-point" />)}
      </svg>
      <div className="chart-labels">{chartLabels.map((label) => <span key={label}>{label}</span>)}</div>
    </div>
  )
}

function App() {
  const [dashboardData, setDashboardData] = useState(initialDashboardData)
  const [isLoading, setIsLoading] = useState(true)
  const [apiError, setApiError] = useState('')
  const [dataSource, setDataSource] = useState('mock')
  const status = formatStatus(dashboardData.status)

  useEffect(() => {
    let isMounted = true

    const refreshTelemetry = async () => {
      setIsLoading(true)
      const result = await getLatestTelemetry()

      if (!isMounted) return

      setApiError(result.error || '')
      setDataSource(result.source)
      setDashboardData((current) => {
        const latest = result.data
        const records = Array.isArray(latest) ? latest : [latest]
        const currentTelemetry = records[0]
        const nextPercentage = Number(currentTelemetry.occupancy_percentage)

        return {
          ...current,
          occupancy: Number(currentTelemetry.occupancy),
          capacity: Number(currentTelemetry.capacity),
          occupancyPercentage: nextPercentage,
          waitTime: Number(currentTelemetry.estimated_wait_minutes),
          inCount: Number(currentTelemetry.people_in),
          outCount: Number(currentTelemetry.people_out),
          status: currentTelemetry.status,
          lastUpdated: new Date(),
          chartPoints: [...current.chartPoints.slice(1), nextPercentage],
          telemetry: records,
        }
      })
      setIsLoading(false)
    }

    refreshTelemetry()
    const telemetryTimer = setInterval(refreshTelemetry, 5000)

    return () => {
      isMounted = false
      clearInterval(telemetryTimer)
    }
  }, [])

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-icon">CC</span><span>CloudCrowd<span>Analytics</span></span></div>
        <nav>
          <a className="active" href="#overview"><span className="nav-icon">/</span>Overview</a>
          <a href="#telemetry"><span className="nav-icon">+</span>Telemetry</a>
          <a href="#locations"><span className="nav-icon">[]</span>Locations</a>
          <a href="#settings"><span className="nav-icon">*</span>Settings</a>
        </nav>
        <div className="sidebar-footer"><span className="connection-dot" />Demo workspace<div>{dataSource === 'api' ? 'Live API mode' : 'Mock data mode'}</div></div>
      </aside>

      <section className="dashboard" id="overview">
        <header className="topbar">
          <div className="eyebrow">Operational overview <span>/</span> Main hall</div>
          <div className="header-actions"><span className="last-updated">Last updated {formatTime(dashboardData.lastUpdated)}</span>{isLoading && <span className="telemetry-loading" role="status"><i />Loading telemetry</span>}{apiError && <span className="telemetry-error" role="status">{apiError} Using mock data.</span>}<button className="icon-button" aria-label="Notifications">!</button><div className="avatar">AS</div></div>
        </header>

        <div className="page-intro">
          <div><p className="kicker">Thursday, 24 October 2024</p><h1>Good morning, Alex.</h1><p className="intro-copy">Here&apos;s how your space is moving today.</p></div>
          <button className="date-button">Today <span>⌄</span></button>
        </div>

        <section className="stats-grid" aria-label="Key metrics">
          <StatCard label="Occupancy" value={dashboardData.occupancy} suffix={` / ${dashboardData.capacity}`} detail={`${dashboardData.occupancyPercentage}% of total capacity`} tone="navy" progress={dashboardData.occupancyPercentage}><span className="people-mark">●●</span></StatCard>
          <StatCard label="Capacity" value={dashboardData.capacity} suffix=" people" detail="Live capacity limit"><span className="ring-mark">◒</span></StatCard>
          <StatusCard status={status} />
          <StatCard label="Est. wait time" value={String(dashboardData.waitTime).padStart(2, '0')} suffix=" min" detail="Updated with live flow"><span className="clock-mark">◷</span></StatCard>
        </section>

        <section className="flow-row">
          <article className="flow-card"><div className="flow-title"><span>People flow</span><span className="muted">Latest interval</span></div><div className="flow-stats"><div><span className="flow-label"><i className="in-dot" />IN</span><strong>{dashboardData.inCount.toLocaleString()}</strong><small>Latest</small></div><div className="flow-divider" /><div><span className="flow-label"><i className="out-dot" />OUT</span><strong>{dashboardData.outCount.toLocaleString()}</strong><small>Latest</small></div></div></article>
          <article className="note-card"><span className="note-icon">i</span><div><strong>Space is filling steadily</strong><p>Peak activity usually starts around 12:30 PM.</p></div><span className="note-arrow">↗</span></article>
        </section>

        <section className="lower-grid">
          <article className="panel chart-panel"><div className="panel-header"><div><p className="kicker">Live trend</p><h2>Occupancy history</h2></div><div className="chart-legend"><span /> Occupancy <button aria-label="More chart options">...</button></div></div><div className="chart-summary"><strong>{dashboardData.occupancyPercentage}%</strong><span>current occupancy</span><b>{dataSource === 'api' ? 'Live' : 'Mock'}</b></div><OccupancyChart points={dashboardData.chartPoints} /></article>
          <article className="panel telemetry-panel" id="telemetry"><div className="panel-header"><div><p className="kicker">Stream</p><h2>Recent telemetry</h2></div><button className="view-button">View all <span>→</span></button></div><div className="table-scroll"><table><thead><tr><th>Time</th><th>Location</th><th>Occupancy</th><th>IN / OUT</th><th>Status</th></tr></thead><tbody>{dashboardData.telemetry.map((row) => { const movement = row.people_in - row.people_out; const statusLabel = formatStatus(row.status); return <tr key={row.timestamp}><td>{formatTime(new Date(row.timestamp))}</td><td>{row.location_id}</td><td><span className="occupancy-number">{row.occupancy_percentage}%</span><span className="bar"><i style={{ width: `${row.occupancy_percentage}%` }} /></span></td><td className={movement >= 0 ? 'positive' : 'negative'}>{row.people_in} / {row.people_out}</td><td><span className={`table-status ${row.status}`}><i />{statusLabel}</span></td></tr> })}</tbody></table></div></article>
        </section>
        <footer className="dashboard-footer">CloudCrowd Analytics <span>•</span> Edge device CC-204 <span>•</span> Data refreshes every 5 seconds</footer>
      </section>
    </main>
  )
}

export default App
