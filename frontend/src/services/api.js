const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL || ''

export const API_BASE_URL = configuredBaseUrl.replace(/\/$/, '')

export const MOCK_TELEMETRY = [
  { location_id: 'library_01', timestamp: '2026-09-17T10:42:18Z', occupancy: 68, capacity: 100, occupancy_percentage: 68, people_in: 12, people_out: 4, estimated_wait_minutes: 8, status: 'yellow' },
  { location_id: 'library_01', timestamp: '2026-09-17T10:40:03Z', occupancy: 51, capacity: 100, occupancy_percentage: 51, people_in: 7, people_out: 3, estimated_wait_minutes: 6, status: 'yellow' },
  { location_id: 'library_01', timestamp: '2026-09-17T10:37:45Z', occupancy: 83, capacity: 100, occupancy_percentage: 83, people_in: 2, people_out: 10, estimated_wait_minutes: 10, status: 'red' },
  { location_id: 'library_01', timestamp: '2026-09-17T10:35:11Z', occupancy: 62, capacity: 100, occupancy_percentage: 62, people_in: 19, people_out: 4, estimated_wait_minutes: 7, status: 'yellow' },
]

function getErrorMessage(error) {
  return error instanceof Error ? error.message : 'Unable to load telemetry.'
}

function normalizeTelemetryRecord(record) {
  if (!record || typeof record !== 'object') {
    return record
  }

  const occupancy = Number(record.occupancy ?? 0)
  const capacity = Number(record.capacity ?? 100)
  const occupancyPercentage = Number(
    record.occupancy_percentage ?? (capacity ? (occupancy / capacity) * 100 : 0),
  )

  return {
    location_id: record.location_id ?? record.facility_id ?? 'library_01',
    timestamp: record.timestamp ?? new Date().toISOString(),
    occupancy,
    capacity,
    occupancy_percentage: occupancyPercentage,
    people_in: Number(record.people_in ?? record.inflow ?? 0),
    people_out: Number(record.people_out ?? record.outflow ?? 0),
    estimated_wait_minutes: Number(record.estimated_wait_minutes ?? record.wait_time ?? 0),
    status: String(record.status ?? 'green').toLowerCase(),
  }
}

async function requestTelemetry(path, fallbackData, options = {}) {
  if (!API_BASE_URL) {
    console.info(`[telemetry] API base URL is not configured; using mock data for ${path}.`)
    return {
      data: Array.isArray(fallbackData) ? fallbackData.map(normalizeTelemetryRecord) : normalizeTelemetryRecord(fallbackData),
      error: null,
      loading: false,
      source: 'mock',
    }
  }

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        Accept: 'application/json',
        ...options.headers,
      },
    })

    if (!response.ok) {
      throw new Error(`Telemetry request failed with status ${response.status}.`)
    }

    const payload = await response.json()
    const normalizedPayload = Array.isArray(payload)
      ? payload.map(normalizeTelemetryRecord)
      : normalizeTelemetryRecord(payload)

    const result = {
      data: normalizedPayload,
      error: null,
      loading: false,
      source: 'api',
    }
    console.info(`[telemetry] API request succeeded: ${path}`, result.data)
    return result
  } catch (error) {
    const result = {
      data: Array.isArray(fallbackData) ? fallbackData.map(normalizeTelemetryRecord) : normalizeTelemetryRecord(fallbackData),
      error: getErrorMessage(error),
      loading: false,
      source: 'mock',
    }
    console.warn(`[telemetry] API request failed: ${path}; using mock data.`, result.error)
    return result
  }
}

export function getTelemetry(options) {
  return requestTelemetry('/telemetry', MOCK_TELEMETRY, options)
}

export function getLatestTelemetry(options) {
  return requestTelemetry('/telemetry/latest', MOCK_TELEMETRY[0], options)
}
