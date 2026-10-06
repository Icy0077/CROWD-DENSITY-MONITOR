# Frontend API Integration Test

**Date:** 2026-09-17  
**Scope:** React dashboard integration with the latest telemetry API response.

## Configuration

The frontend reads the API Gateway base URL from `VITE_API_BASE_URL`. A non-secret template is provided in `frontend/.env.example`. The request appends `/telemetry/latest` and sends `Accept: application/json`.

## Field verification

The dashboard consumes the canonical fields from `docs/telemetry-schema.md`:

| Schema field | Dashboard use |
| --- | --- |
| `location_id` | Recent telemetry location |
| `timestamp` | Last-updated time and telemetry row time |
| `occupancy` | Current number of people |
| `capacity` | Capacity limit |
| `occupancy_percentage` | Progress bar and current percentage |
| `people_in` | IN count |
| `people_out` | OUT count |
| `estimated_wait_minutes` | Estimated wait card |
| `status` | Status card and telemetry status |

## Expected results

- A successful API response updates the existing dashboard with live occupancy, capacity, status, IN/OUT counts, wait time, timestamp, and location.
- A loading indicator displays `Loading telemetry` during the request.
- HTTP failures or network errors display the API error and use schema-shaped mock telemetry.
- The sidebar identifies whether the current data source is `Live API mode` or `Mock data mode`.
- No credentials or secrets are embedded in the frontend.
- The dashboard layout and existing visual structure are unchanged.

## Verification status

The source integration was reviewed against the API response schema and the API service normalizes both API and fallback records to the canonical field names. The production build could not be executed in this environment because Node.js/npm is not installed or available on `PATH`.