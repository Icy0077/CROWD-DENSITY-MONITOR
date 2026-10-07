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
  return <section className="facility-intro" aria-labelledby="facility-title"><div><p className="eyebrow">Facility 01</p><h1 id="facility-title">{data.facilityId || 'Awaiting live telemetry'}</h1><p className="intro-copy">A live reading of movement through the monitored space.</p></div><p className={`quiet-status status-${telemetryStatus}`}><span aria-hidden="true">●</span> {telemetryStatus}</p></section>
}

function OccupancyReading({ data }) {
  const utilization = Number.isFinite(data.utilization) ? Math.max(0, Math.min(100, data.utilization)) : null
  return <section className="occupancy-section" aria-labelledby="occupancy-title"><div className="occupancy-copy"><p className="eyebrow" id="occupancy-title">Current occupancy</p><div className="occupancy-hero" aria-label={`${data.occupancy ?? 'unknown'} people inside out of ${data.capacity ?? 'unknown'} capacity`}><strong>{data.occupancy ?? '—'}</strong><span>/ {data.capacity ?? '—'}</span></div><p className="occupancy-caption">People inside</p><p className="occupancy-percent">{utilization === null ? 'Waiting for a live reading' : `${utilization}% of capacity`}</p></div><div className="occupancy-aside"><span>Latest reading</span><strong>{data.lastUpdated ? formatTime(data.lastUpdated) : '—'}</strong><span>Reporting interval · 5 seconds</span></div></section>
}

function CapacityReading({ data }) {
  const value = Number.isFinite(data.utilization) ? Math.max(0, Math.min(100, data.utilization)) : 0
  const status = data.status || 'unknown'
  const message = status === 'red' ? 'The space is approaching its configured limit.' : status === 'yellow' ? 'The space is filling; continue to monitor movement.' : status === 'green' ? 'Room remains comfortably below capacity.' : 'Capacity status will appear with live telemetry.'
  return <section className="capacity-section" aria-labelledby="capacity-title"><div className="section-rule-heading"><p className="eyebrow" id="capacity-title">Capacity reading</p><h2>How full is the space?</h2></div><div className="capacity-reading"><strong>{Number.isFinite(data.utilization) ? `${value}%` : '—'}</strong><span>{data.occupancy ?? '—'} of {data.capacity ?? '—'} people</span></div><div className={`capacity-line capacity-${status}`}><span style={{ width: `${value}%` }} /></div><div className="capacity-footer"><span className={`status-note status-note-${status}`}><i />{status.toUpperCase()}</span><p>{message}</p></div></section>
}

export default function App() {
  if (window.location.pathname !== '/' && window.location.pathname !== '') return <NotFound />
  const [data, setData] = useState(initialState); const [isLoading, setIsLoading] = useState(true); const [apiError, setApiError] = useState(''); const [currentTime, setCurrentTime] = useState(() => new Date()); const [lastMovement, setLastMovement] = useState(null); const inFlight = useRef(false); const lastTelemetry = useRef(null)
  const telemetryStatus = getTelemetryStatus(data.lastUpdated, apiError, currentTime)
  const fetchTelemetry = useCallback(async () => { if (inFlight.current) return; inFlight.current = true; setIsLoading(true); try { const result = await getLatestTelemetry(); setApiError(result.error || ''); if (result.data) { const t = result.data; const timestamp = new Date(t.timestamp); const changed = telemetryChanged(lastTelemetry.current, t); if (changed) { lastTelemetry.current = t; setLastMovement({ timestamp: t.timestamp, inflow: t.inflow, outflow: t.outflow }) } setData((previous) => ({ ...previous, facilityId: t.facility_id, occupancy: t.occupancy, capacity: t.capacity, utilization: t.utilization, estimatedWaitTime: t.estimated_wait_time, inflow: t.inflow, outflow: t.outflow, status: t.status, lastUpdated: timestamp, chartPoints: changed ? [...previous.chartPoints.slice(-(MAX_CHART_POINTS - 1)), t.utilization] : previous.chartPoints, chartLabels: changed ? [...previous.chartLabels.slice(-(MAX_CHART_POINTS - 1)), formatTime(timestamp)] : previous.chartLabels, telemetry: [t], activityLog: changed ? [t, ...previous.activityLog.slice(0, MAX_ACTIVITY_ENTRIES - 1)] : previous.activityLog })) } } finally { inFlight.current = false; setIsLoading(false) } }, [])
  useEffect(() => { const timer = setInterval(() => setCurrentTime(new Date()), 1000); return () => clearInterval(timer) }, [])
  useEffect(() => { fetchTelemetry(); const timer = setInterval(fetchTelemetry, POLL_INTERVAL); return () => clearInterval(timer) }, [fetchTelemetry])
  const showSkeleton = isLoading && data.lastUpdated === null && !apiError
  return <div className="app-container"><Header currentTime={currentTime} lastTelemetryAt={data.lastUpdated} telemetryStatus={telemetryStatus} /><main className="report-main">{showSkeleton ? <><SkeletonCard /><SkeletonChartPanel /></> : <><ReportIntro data={data} telemetryStatus={telemetryStatus} /><OccupancyReading data={data} /><MovementField inflow={data.inflow} outflow={data.outflow} event={lastMovement} /><CapacityReading data={data} /><LiveActivity telemetry={data.telemetry} activityLog={data.activityLog} /><TrendChart points={data.chartPoints} labels={data.chartLabels} /><SystemStatus telemetryStatus={telemetryStatus} apiError={apiError} lastTelemetryAt={data.lastUpdated} currentTime={currentTime} onRetry={fetchTelemetry} /><InputSourceSettings /></>}</main><footer className="report-footer">CloudCrowd Analytics <span>·</span> aggregate telemetry, refreshed every 5 seconds</footer></div>
}
