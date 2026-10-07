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
const TELEMETRY_VALUE_FIELDS = ['facility_id', 'timestamp', 'occupancy', 'capacity', 'inflow', 'outflow', 'estimated_wait_time', 'status', 'utilization']
const initialState = { facilityId: '', occupancy: null, capacity: null, utilization: null, estimatedWaitTime: null, inflow: null, outflow: null, status: null, lastUpdated: null, chartPoints: [], chartLabels: [], telemetry: [], activityLog: [] }

function formatTime(date) { return !date || Number.isNaN(date.getTime()) ? '—' : date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }).toUpperCase() }
function telemetryChanged(previous, next) { return !previous || TELEMETRY_VALUE_FIELDS.some((field) => previous[field] !== next[field]) }
function getTelemetryStatus(lastTelemetryAt, apiError, now) {
  if (apiError) return 'disconnected'
  if (!lastTelemetryAt) return 'stale'
  return now.getTime() - lastTelemetryAt.getTime() <= TELEMETRY_STALE_AFTER_MS ? 'live' : 'stale'
}

function ReportIntro({ data, telemetryStatus }) {
  const summary = !data.lastUpdated
    ? 'Live crowd metrics will appear when telemetry is available.'
    : telemetryStatus === 'disconnected'
      ? 'The dashboard cannot reach the telemetry service. Showing the last received reading.'
      : telemetryStatus === 'stale'
        ? 'Telemetry has not refreshed recently. Check the connection before acting on these readings.'
        : data.status === 'red'
          ? 'Crowd levels are near the configured capacity limit.'
          : data.status === 'yellow'
            ? 'Crowd levels are rising. Review the live flow and queue estimate.'
            : data.status === 'green'
              ? 'Crowd levels are within the configured capacity.'
              : 'Live crowd metrics from your monitored space.'

  const facilityName = data.facilityId === 'facility-1' ? 'Facility 1' : data.facilityId || 'Main Facility'

  return <section className="facility-intro" aria-labelledby="facility-title"><div><p className="eyebrow">Real-time crowd intelligence</p><h1 id="facility-title">{facilityName}</h1><p className="intro-copy">{summary}</p></div><p className={`quiet-status status-${telemetryStatus}`}><span aria-hidden="true">●</span> {telemetryStatus}</p></section>
}

function FloatingNav() {
  return <nav className="floating-nav" aria-label="Primary navigation"><a className="nav-active" href="#overview"><span>⌂</span>Overview</a><a href="#sources"><span>⌁</span>Sources</a></nav>
}

function EdgeVision({ occupancy, telemetryStatus }) {
  return <section className="edge-vision" aria-labelledby="edge-vision-title"><div className="edge-vision-heading"><div><p className="eyebrow">Local processing</p><h2 id="edge-vision-title">Edge Vision</h2></div><span className={`edge-status edge-status-${telemetryStatus}`}><i /> {telemetryStatus === 'live' ? 'Telemetry receiving' : telemetryStatus}</span></div><div className="edge-vision-grid"><div><span className="edge-label">Camera processing</span><strong>On edge device</strong><small>Camera → YOLO/ByteTrack → telemetry</small></div><div><span className="edge-label">People detected</span><strong>{Number.isFinite(occupancy) ? occupancy : '—'}</strong><small>Aggregate count from the latest reading</small></div><div><span className="edge-label">Video stream</span><strong>Local only</strong><small>The dashboard does not receive raw camera frames.</small></div></div></section>
}

function PriorityReadings({ data }) {
  const utilization = Number.isFinite(data.utilization) ? Math.max(0, Math.min(100, data.utilization)) : null
  const status = data.status || 'unknown'
  const waitTime = Number.isFinite(data.estimatedWaitTime) ? data.estimatedWaitTime : null
  const statusLabel = { green: 'Within limit', yellow: 'Monitor', red: 'Near limit', unknown: 'Status unavailable' }[status]

  return <section className="priority-grid" aria-label="Current crowd metrics">
    <article className="priority-card occupancy-priority" aria-labelledby="occupancy-title">
      <p className="eyebrow" id="occupancy-title">People inside</p>
      <div className="priority-value occupancy-priority-value" aria-label={`${data.occupancy ?? 'unknown'} people inside out of ${data.capacity ?? 'unknown'} capacity`}>
        <strong>{data.occupancy ?? '—'}</strong><span> / {data.capacity ?? '—'}</span>
      </div>
      <p className="priority-caption">{utilization === null ? 'Waiting for a live reading' : `${utilization}% of available capacity`}</p>
      <div className={`priority-capacity capacity-${status}`} role="progressbar" aria-label="Capacity used" aria-valuenow={utilization ?? undefined} aria-valuemin="0" aria-valuemax="100">
        <span style={{ width: `${utilization ?? 0}%` }} />
      </div>
      <div className="priority-foot">
        <span className={`status-note status-note-${status}`}><i />{statusLabel}</span>
        <span>Updated {data.lastUpdated ? formatTime(data.lastUpdated) : '—'}</span>
      </div>
    </article>
    <article className="priority-card queue-priority" aria-labelledby="queue-time-title">
      <p className="eyebrow" id="queue-time-title">Estimated queue time</p>
      <div className="priority-value queue-priority-value">
        <strong>{waitTime === null ? '—' : waitTime}</strong><span>{waitTime === null ? 'No estimate' : 'min'}</span>
      </div>
      <p className="priority-caption">{waitTime === null ? 'Waiting for a queue estimate' : 'Estimated from the latest crowd telemetry'}</p>
      <span className="queue-refresh">Refreshes with live readings</span>
    </article>
  </section>
}

export default function App() {
  if (window.location.pathname !== '/' && window.location.pathname !== '') return <NotFound />
  const [data, setData] = useState(initialState); const [isLoading, setIsLoading] = useState(true); const [apiError, setApiError] = useState(''); const [currentTime, setCurrentTime] = useState(() => new Date()); const [lastMovement, setLastMovement] = useState(null); const inFlight = useRef(false); const lastTelemetry = useRef(null)
  const telemetryStatus = getTelemetryStatus(data.lastUpdated, apiError, currentTime)
  const fetchTelemetry = useCallback(async () => { if (inFlight.current) return; inFlight.current = true; setIsLoading(true); try { const result = await getLatestTelemetry(); setApiError(result.error || ''); if (result.data) { const t = result.data; const timestamp = new Date(t.timestamp); const changed = telemetryChanged(lastTelemetry.current, t); if (changed) { lastTelemetry.current = t; setLastMovement({ timestamp: t.timestamp, inflow: t.inflow, outflow: t.outflow }) } setData((previous) => ({ ...previous, facilityId: t.facility_id, occupancy: t.occupancy, capacity: t.capacity, utilization: t.utilization, estimatedWaitTime: t.estimated_wait_time, inflow: t.inflow, outflow: t.outflow, status: t.status, lastUpdated: timestamp, chartPoints: changed ? [...previous.chartPoints.slice(-(MAX_CHART_POINTS - 1)), t.utilization] : previous.chartPoints, chartLabels: changed ? [...previous.chartLabels.slice(-(MAX_CHART_POINTS - 1)), formatTime(timestamp)] : previous.chartLabels, telemetry: [t], activityLog: changed ? [t, ...previous.activityLog.slice(0, MAX_ACTIVITY_ENTRIES - 1)] : previous.activityLog })) } } finally { inFlight.current = false; setIsLoading(false) } }, [])
  useEffect(() => { const timer = setInterval(() => setCurrentTime(new Date()), 1000); return () => clearInterval(timer) }, [])
  useEffect(() => { fetchTelemetry(); const timer = setInterval(fetchTelemetry, POLL_INTERVAL); return () => clearInterval(timer) }, [fetchTelemetry])
  const showSkeleton = isLoading && data.lastUpdated === null && !apiError
  return <div className="app-container"><Header currentTime={currentTime} lastTelemetryAt={data.lastUpdated} telemetryStatus={telemetryStatus} /><FloatingNav /><main className="report-main" id="overview">{showSkeleton ? <><SkeletonCard /><SkeletonChartPanel /></> : <><ReportIntro data={data} telemetryStatus={telemetryStatus} /><PriorityReadings data={data} /><MovementField inflow={data.inflow} outflow={data.outflow} event={lastMovement} /><LiveActivity telemetry={data.telemetry} activityLog={data.activityLog} /><TrendChart points={data.chartPoints} labels={data.chartLabels} /><SystemStatus telemetryStatus={telemetryStatus} apiError={apiError} lastTelemetryAt={data.lastUpdated} currentTime={currentTime} onRetry={fetchTelemetry} /><details className="technical-details"><summary>Camera and edge processing details</summary><EdgeVision occupancy={data.occupancy} telemetryStatus={telemetryStatus} /></details><div id="sources"><InputSourceSettings /></div></>}</main><footer className="report-footer">CloudCrowd Analytics <span>·</span> aggregate telemetry, refreshed every 5 seconds</footer></div>
}
