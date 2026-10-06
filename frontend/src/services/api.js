const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL || ''

export const API_BASE_URL = configuredBaseUrl.replace(/\/$/, '')
export const FACILITY_ID = import.meta.env.VITE_FACILITY_ID || ''

const REQUIRED_TELEMETRY_FIELDS = [
  'facility_id',
  'timestamp',
  'occupancy',
  'capacity',
  'inflow',
  'outflow',
  'estimated_wait_time',
  'status',
  'utilization',
]

function firstDefined(record, ...fields) {
  return fields.map((field) => record[field]).find((value) => value !== undefined && value !== null)
}

function getErrorMessage(error) {
  return error instanceof Error && error.message === 'Telemetry response is invalid.'
    ? error.message
    : 'Unable to load telemetry right now.'
}

function normalizeTelemetryRecord(record) {
  if (!record || typeof record !== 'object') {
    throw new Error('Telemetry response must be an object.')
  }

  const normalized = {
    facility_id: firstDefined(record, 'facility_id', 'location_id'),
    timestamp: record.timestamp,
    occupancy: record.occupancy,
    capacity: record.capacity,
    inflow: firstDefined(record, 'inflow', 'people_in'),
    outflow: firstDefined(record, 'outflow', 'people_out'),
    estimated_wait_time: firstDefined(record, 'estimated_wait_time', 'estimated_wait_minutes'),
    status: record.status,
    utilization: firstDefined(record, 'utilization', 'occupancy_percentage'),
  }
  const missingFields = REQUIRED_TELEMETRY_FIELDS.filter((field) => normalized[field] === undefined || normalized[field] === null)
  if (missingFields.length) {
    throw new Error('Telemetry response is invalid.')
  }

  const numericFields = ['occupancy', 'capacity', 'inflow', 'outflow', 'estimated_wait_time', 'utilization']
  if (!numericFields.every((field) => Number.isFinite(Number(normalized[field]))) || Number.isNaN(new Date(normalized.timestamp).getTime())) {
    throw new Error('Telemetry response is invalid.')
  }

  return {
    facility_id: String(normalized.facility_id),
    timestamp: normalized.timestamp,
    occupancy: Number(normalized.occupancy),
    capacity: Number(normalized.capacity),
    inflow: Number(normalized.inflow),
    outflow: Number(normalized.outflow),
    estimated_wait_time: Number(normalized.estimated_wait_time),
    status: ['green', 'yellow', 'red', 'unknown'].includes(String(normalized.status).toLowerCase()) ? String(normalized.status).toLowerCase() : 'unknown',
    utilization: Number(normalized.utilization),
  }
}

async function requestTelemetry(path, options = {}) {
  if (!API_BASE_URL) {
    return {
      data: null,
      error: 'VITE_API_BASE_URL is not configured.',
      loading: false,
      source: 'api',
    }
  }

  if (!FACILITY_ID) {
    return {
      data: null,
      error: 'VITE_FACILITY_ID is not configured.',
      loading: false,
      source: 'api',
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

    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      throw new Error(payload?.error || `Telemetry request failed with status ${response.status}.`)
    }

    return {
      data: normalizeTelemetryRecord(payload),
      error: null,
      loading: false,
      source: 'api',
    }
  } catch (error) {
    return {
      data: null,
      error: getErrorMessage(error),
      loading: false,
      source: 'api',
    }
  }
}

export function getLatestTelemetry(options) {
  const query = new URLSearchParams({ facility_id: FACILITY_ID })
  return requestTelemetry(`/telemetry/latest?${query.toString()}`, options)
}
