import { useCallback, useEffect, useRef, useState } from 'react'
import { getLatestTelemetry } from './services/api'
import Header from './components/Header'
import LiveActivity from './components/LiveActivity'
import TrendChart from './components/TrendChart'
import SystemStatus from './components/SystemStatus'
import InputSourceSettings from './components/InputSourceSettings'
import MovementField from './components/MovementField'
import NotFound from './components/NotFound'
import { SkeletonCard, SkeletonChartPanel } from './components/LoadingSkeleton'

const POLL_INTERVAL = 5000
const DEFAULT_STALE_AFTER_MS = 15000
const configuredStaleAfterMs = Number(import.meta.env.VITE_TELEMETRY_STALE_AFTER_MS)
const TELEMETRY_STALE_AFTER_MS = Number.isFinite(configuredStaleAfterMs) && configuredStaleAfterMs > 0 ? configuredStaleAfterMs : DEFAULT_STALE_AFTER_MS
const MAX_ACTIVITY_ENTRIES = 20
const MAX_CHART_POINTS = 24
const CALCULATION_OCCUPANCY_LIMIT = 3
const TELEMETRY_VALUE_FIELDS = ['facility_id', 'timestamp', 'occupancy', 'capacity', 'inflow', 'outflow', 'estimated_wait_time', 'status', 'utilization']
const initialState = { facilityId: '', occupancy: null, capacity: null, utilization: null, estimatedWaitTime: null, inflow: null, outflow: null, status: null, lastUpdated: null, chartPoints: [], chartLabels: [], telemetry: [], activityLog: [] }

function formatTime(date) { return !date || Number.isNaN(date.getTime()) ? '—' : date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }).toUpperCase() }
function telemetryChanged(previous, next) { return !previous || TELEMETRY_VALUE_FIELDS.some((field) => previous[field] !== next[field]) }
function getTelemetryStatus(lastTelemetryAt, apiError, now) {
  if (apiError) return 'disconnected'
  if (!lastTelemetryAt) return 'stale'
  return now.getTime() - lastTelemetryAt.getTime() <= TELEMETRY_STALE_AFTER_MS ? 'live' : 'stale'
}

function getCalculationStatus(utilization) {
  if (utilization < 50) return 'green'
  if (utilization <= 80) return 'yellow'
  return 'red'
}

function applyCalculationLimit(telemetry) {
  const utilization = Math.round((telemetry.occupancy / CALCULATION_OCCUPANCY_LIMIT) * 100)
  return {
    ...telemetry,
    capacity: CALCULATION_OCCUPANCY_LIMIT,
    utilization,
    status: getCalculationStatus(utilization),
  }
}

function ReportIntro({ data, telemetryStatus }) {
  const summary = !data.lastUpdated
    ? 'Live crowd metrics will appear when telemetry is available.'
    : telemetryStatus === 'disconnected'
      ? 'The dashboard cannot reach the telemetry service. Showing the last received reading.'
      : telemetryStatus === 'stale'
        ? 'Last-known telemetry is still displayed while the service catches up. Treat these values as stale until the next refresh.'
        : data.status === 'red'
          ? 'Telemetry recovered and is updating normally. Crowd levels are approaching the calculated threshold.'
          : data.status === 'yellow'
            ? 'Telemetry recovered and is updating normally. Crowd levels are rising. Review the current flow and queue estimate.'
            : data.status === 'green'
              ? 'Telemetry recovered and is updating normally. Crowd levels remain within the calculated threshold.'
              : 'Live crowd metrics from your monitored space.'

  const statusText = telemetryStatus === 'live' ? 'Live telemetry' : telemetryStatus === 'stale' ? 'Telemetry stale' : telemetryStatus === 'disconnected' ? 'Telemetry disconnected' : 'Awaiting telemetry'

  return <section className="facility-intro" aria-labelledby="facility-title"><div><p className="eyebrow">Real-time crowd intelligence</p><h1 id="facility-title">Facility 1</h1><p className="intro-copy">{summary}</p></div><p className={`quiet-status status-${telemetryStatus}`}><span aria-hidden="true">●</span> {statusText}</p></section>
}

function PrimaryNav({ page, onNavigate }) {
  const items = [
    { id: 'overview', label: 'Overview' },
    { id: 'sources', label: 'Input Sources' },
    { id: 'about', label: 'About' },
  ]

  return <nav className="floating-nav" aria-label="Primary navigation">
    {items.map((item) => (
      <button
        key={item.id}
        type="button"
        className={page === item.id ? 'nav-active' : ''}
        onClick={() => onNavigate(item.id)}
      >
        <span aria-hidden="true">{item.id === 'overview' ? '⌂' : item.id === 'sources' ? '⌁' : '◌'}</span>
        {item.label}
      </button>
    ))}
  </nav>
}

function PriorityReadings({ data, telemetryStatus }) {
  const utilization = Number.isFinite(data.utilization) ? Math.max(0, Math.min(100, data.utilization)) : null
  const status = data.status || 'unknown'
  const waitTime = Number.isFinite(data.estimatedWaitTime) ? data.estimatedWaitTime : null
  const statusLabel = { green: 'Normal', yellow: 'Moderate', red: 'High', unknown: 'Status unavailable' }[status]
  const isStale = telemetryStatus === 'stale' || telemetryStatus === 'disconnected'

  const queueCue = waitTime === null
    ? isStale ? 'Last-known estimate only' : 'Waiting for a live estimate'
    : waitTime <= 3
      ? 'Minimal delay expected'
      : waitTime <= 10
        ? 'Moderate waits likely'
        : 'Queue pressure visible'

  const occupancyLabel = isStale ? 'Last-known occupancy' : 'Current occupancy'
  const thresholdLabel = isStale ? 'Reference threshold' : 'Calculated threshold'

  return <section className="priority-grid" aria-label="Current crowd metrics">
    <article className={`priority-card occupancy-priority ${isStale ? 'is-stale' : ''}`} aria-labelledby="occupancy-title">
      <p className="eyebrow" id="occupancy-title">{occupancyLabel}</p>
      <div className="priority-value occupancy-priority-value" aria-label={`${data.occupancy ?? 'unknown'} people inside out of ${data.capacity ?? 'unknown'} capacity`}>
        <strong>{data.occupancy ?? '—'}</strong><span> / {data.capacity ?? '—'}</span>
      </div>
      <p className="priority-caption">{utilization === null ? 'Waiting for a live reading' : `${utilization}% of the ${thresholdLabel.toLowerCase()}`}</p>
      <div className={`priority-capacity capacity-${status}`} role="progressbar" aria-label="Capacity used" aria-valuenow={utilization ?? undefined} aria-valuemin="0" aria-valuemax="100">
        <span style={{ width: `${utilization ?? 0}%` }} />
      </div>
      <div className="priority-foot">
        <span className={`status-note status-note-${status}`}><i />{statusLabel}</span>
        <span>{isStale ? 'Last update' : 'Updated'} {data.lastUpdated ? formatTime(data.lastUpdated) : '—'}</span>
      </div>
    </article>

    <article className={`priority-card queue-priority ${isStale ? 'is-stale' : ''}`} aria-labelledby="queue-title">
      <p className="eyebrow" id="queue-title">Queue time</p>
      <div className="priority-value queue-priority-value" aria-label={`${waitTime === null ? 'unknown' : waitTime} minutes estimated wait`}>
        <strong>{waitTime === null ? '—' : waitTime}</strong><span> min</span>
      </div>
      <p className="priority-caption">{queueCue}</p>
      <div className="priority-foot">
        <span className={`status-note status-note-${status}`}><i />{statusLabel}</span>
        <span>{isStale ? 'Last-known estimate' : 'Live estimate'}</span>
      </div>
    </article>

    <article className="priority-card flow-priority" aria-labelledby="flow-title">
      <p className="eyebrow" id="flow-title">Latest movement</p>
      <div className="flow-reading-grid">
        <div><span>Inflow</span><strong>{data.inflow ?? '—'}</strong></div>
        <div><span>Outflow</span><strong>{data.outflow ?? '—'}</strong></div>
      </div>
      <p className="priority-caption">People counted during the latest reporting interval.</p>
      <div className="wait-reading"><span>Net flow</span><strong>{data.inflow === null || data.outflow === null ? 'No movement data yet' : `${Math.max(0, (data.inflow || 0) - (data.outflow || 0))} people`}</strong></div>
    </article>
  </section>
}

function OverviewPage({ data, telemetryStatus, isLoading, apiError, currentTime, lastMovement, fetchTelemetry }) {
  const showSkeleton = isLoading && data.lastUpdated === null && !apiError
  return <>
    {showSkeleton ? <><SkeletonCard /><SkeletonChartPanel /></> : <>
      <section className="editorial-hero" aria-labelledby="overview-hero-title">
        <div className="hero-copy">
          <p className="eyebrow">Real-time crowd visibility</p>
          <h1 id="overview-hero-title">Understand movement in your monitored space.</h1>
          <p className="hero-subheading">Real-time people counting, movement tracking and crowd visibility powered by computer vision.</p>
        </div>
        <aside className="hero-status-panel">
          <p className="status-kicker">System status</p>
          <strong>{telemetryStatus === 'live' ? 'Connected' : telemetryStatus === 'stale' ? 'Recovering' : telemetryStatus === 'disconnected' ? 'Disconnected' : 'Awaiting data'}</strong>
          <span>{data.lastUpdated ? formatTime(data.lastUpdated) : 'Waiting for telemetry'}</span>
        </aside>
      </section>
      <ReportIntro data={data} telemetryStatus={telemetryStatus} />
      <PriorityReadings data={data} telemetryStatus={telemetryStatus} />
      <MovementField occupancy={data.occupancy} inflow={data.inflow} outflow={data.outflow} event={lastMovement} />
      <LiveActivity telemetry={data.telemetry} activityLog={data.activityLog} />
      <TrendChart points={data.chartPoints} labels={data.chartLabels} />
      <SystemStatus telemetryStatus={telemetryStatus} apiError={apiError} lastTelemetryAt={data.lastUpdated} currentTime={currentTime} onRetry={fetchTelemetry} />
    </>}
  </>
}

function InputSourcesPage() {
  return <section className="page-section input-sources-page" aria-labelledby="input-sources-page-title">
    <div className="page-heading"><div><p className="eyebrow">Edge device control</p><h1 id="input-sources-page-title">Input Sources</h1><p>Choose where CrowdCloud receives its video stream.</p></div><span className="page-note">Raw video stays on the edge device.</span></div>
    <InputSourceSettings />
  </section>
}

function AboutPage() {
  return <section className="page-section about-page" aria-labelledby="about-page-title">
    <div className="page-heading about-heading"><div><p className="eyebrow">About</p><h1 id="about-page-title">CloudCrowd Analytics</h1><p>Real-time crowd visibility through computer vision.</p></div></div>

    <div className="about-grid">
      <article className="about-panel">
        <h2>What is CloudCrowd?</h2>
        <p>CloudCrowd Analytics is a real-time crowd monitoring system that uses computer vision to detect and track people moving through a monitored space.</p>
      </article>
      <article className="about-panel">
        <h2>How it works</h2>
        <ol className="step-list">
          <li><span>Camera</span><small>A camera provides the live video feed.</small></li>
          <li><span>Detection</span><small>YOLO identifies people in the video.</small></li>
          <li><span>Tracking</span><small>ByteTrack follows detected people across frames.</small></li>
          <li><span>Movement</span><small>The system determines occupancy, inflow and outflow.</small></li>
          <li><span>Cloud</span><small>Telemetry is transmitted to the cloud.</small></li>
          <li><span>Dashboard</span><small>The dashboard presents the latest crowd state.</small></li>
        </ol>
      </article>
    </div>

    <article className="architecture-panel">
      <h2>Architecture</h2>
      <div className="architecture-flow" aria-label="System architecture">
        <span>Camera</span><span>Edge Vision</span><span>YOLO + ByteTrack</span><span>Telemetry</span><span>AWS IoT</span><span>Lambda</span><span>DynamoDB</span><span>API</span><span>CloudCrowd Dashboard</span>
      </div>
      <p>Raw video remains at the edge. Telemetry is sent through the current cloud pipeline and surfaced in the dashboard.</p>
    </article>

    <div className="about-grid">
      <article className="about-panel">
        <h2>Privacy by Design</h2>
        <p>CloudCrowd is designed to keep raw video processing at the edge, sending only telemetry and derived movement signals to the cloud layer.</p>
      </article>
      <article className="about-panel">
        <h2>Supported inputs</h2>
        <ul className="source-list">
          <li><strong>Webcam</strong><small>Available</small></li>
          <li><strong>USB Camera</strong><small>Available</small></li>
          <li><strong>Wi-Fi Camera</strong><small>Requires configuration</small></li>
          <li><strong>CCTV / RTSP</strong><small>Requires configuration</small></li>
          <li><strong>Phone</strong><small>Available when paired</small></li>
          <li><strong>Local Video File</strong><small>Available</small></li>
        </ul>
      </article>
    </div>
  </section>
}

export default function App() {
  const validPaths = ['/', '/overview', '/sources', '/about']
  const hashPage = window.location.hash === '#sources' ? 'sources' : window.location.hash === '#about' ? 'about' : 'overview'
  if (!validPaths.includes(window.location.pathname) && !['#overview', '#sources', '#about'].includes(window.location.hash)) return <NotFound />
  const initialPage = window.location.hash === '#sources' || window.location.pathname === '/sources'
    ? 'sources'
    : window.location.hash === '#about' || window.location.pathname === '/about'
      ? 'about'
      : 'overview'
  const [page, setPage] = useState(initialPage)
  const [data, setData] = useState(initialState)
  const [isLoading, setIsLoading] = useState(true)
  const [apiError, setApiError] = useState('')
  const [currentTime, setCurrentTime] = useState(() => new Date())
  const [lastMovement, setLastMovement] = useState(null)
  const inFlight = useRef(false)
  const lastTelemetry = useRef(null)
  const telemetryStatus = getTelemetryStatus(data.lastUpdated, apiError, currentTime)

  const fetchTelemetry = useCallback(async () => {
    if (inFlight.current) return
    inFlight.current = true
    setIsLoading(true)
    try {
      const result = await getLatestTelemetry()
      setApiError(result.error || '')
      if (result.data) {
        const sourceTelemetry = result.data
        const t = applyCalculationLimit(sourceTelemetry)
        const timestamp = new Date(sourceTelemetry.timestamp)
        const previousTelemetry = lastTelemetry.current
        const changed = telemetryChanged(previousTelemetry, sourceTelemetry)
        const isNewTelemetry = Boolean(previousTelemetry && previousTelemetry.timestamp !== sourceTelemetry.timestamp)
        if (isNewTelemetry && (sourceTelemetry.inflow > 0 || sourceTelemetry.outflow > 0)) {
          lastTelemetry.current = sourceTelemetry
          setLastMovement({ key: `${sourceTelemetry.timestamp}:${sourceTelemetry.inflow}:${sourceTelemetry.outflow}`, timestamp: sourceTelemetry.timestamp, inflow: sourceTelemetry.inflow, outflow: sourceTelemetry.outflow })
        }
        if (!previousTelemetry) lastTelemetry.current = sourceTelemetry
        else if (changed) lastTelemetry.current = sourceTelemetry
        setData((previous) => ({ ...previous, facilityId: t.facility_id, occupancy: t.occupancy, capacity: t.capacity, utilization: t.utilization, estimatedWaitTime: t.estimated_wait_time, inflow: t.inflow, outflow: t.outflow, status: t.status, lastUpdated: timestamp, chartPoints: changed ? [...previous.chartPoints.slice(-(MAX_CHART_POINTS - 1)), t.utilization] : previous.chartPoints, chartLabels: changed ? [...previous.chartLabels.slice(-(MAX_CHART_POINTS - 1)), formatTime(timestamp)] : previous.chartLabels, telemetry: [t], activityLog: changed ? [t, ...previous.activityLog.slice(0, MAX_ACTIVITY_ENTRIES - 1)] : previous.activityLog }))
      }
    } finally {
      inFlight.current = false
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])
  useEffect(() => {
    fetchTelemetry()
    const timer = setInterval(fetchTelemetry, POLL_INTERVAL)
    return () => clearInterval(timer)
  }, [fetchTelemetry])
  useEffect(() => {
    const handleHashChange = () => setPage(window.location.hash === '#sources' || window.location.pathname === '/sources'
    ? 'sources'
    : window.location.hash === '#about' || window.location.pathname === '/about'
      ? 'about'
      : 'overview')
    window.addEventListener('hashchange', handleHashChange)
    window.addEventListener('popstate', handleHashChange)
    return () => {
      window.removeEventListener('hashchange', handleHashChange)
      window.removeEventListener('popstate', handleHashChange)
    }
  }, [])

  const navigate = (nextPage) => {
    setPage(nextPage)
    const targetPath = nextPage === 'sources' ? '/sources' : nextPage === 'about' ? '/about' : '/'
    window.history.pushState({}, '', targetPath)
  }

  return <div className="app-container">
    <Header currentTime={currentTime} lastTelemetryAt={data.lastUpdated} telemetryStatus={telemetryStatus} page={page} onNavigate={navigate} />
    <main className="report-main" id={page === 'overview' ? 'overview' : page === 'sources' ? 'sources' : 'about'}>
      {page === 'overview'
        ? <OverviewPage data={data} telemetryStatus={telemetryStatus} isLoading={isLoading} apiError={apiError} currentTime={currentTime} lastMovement={lastMovement} fetchTelemetry={fetchTelemetry} />
        : page === 'sources'
          ? <InputSourcesPage />
          : <AboutPage />}
    </main>
    <footer className="report-footer">CloudCrowd Analytics <span>·</span> real-time crowd visibility through computer vision</footer>
  </div>
}
