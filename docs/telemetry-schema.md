# Telemetry Response Schema

This document defines the shared telemetry response format for CloudCrowdAnalytics. It is transport-agnostic and does not require an AWS, API Gateway, or backend integration.

## Example response

```json
{
  "location_id": "library_01",
  "timestamp": "2026-09-17T10:30:00Z",
  "occupancy": 42,
  "capacity": 100,
  "occupancy_percentage": 42,
  "people_in": 8,
  "people_out": 5,
  "estimated_wait_minutes": 5,
  "status": "green"
}
```

## Fields

| Field | Type | Description |
| --- | --- | --- |
| `location_id` | string | Stable identifier for the monitored location. |
| `timestamp` | string | UTC timestamp in ISO 8601 format indicating when the telemetry was recorded. |
| `occupancy` | integer | Current number of people detected at the location. Must be zero or greater and should not exceed `capacity`. |
| `capacity` | integer | Maximum supported number of people for the location. Must be greater than zero. |
| `occupancy_percentage` | number | Current occupancy as a percentage of capacity, normally calculated as `occupancy / capacity * 100`. |
| `people_in` | integer | Number of people entering during the reporting interval. Must be zero or greater. |
| `people_out` | integer | Number of people leaving during the reporting interval. Must be zero or greater. |
| `estimated_wait_minutes` | integer | Estimated wait time in minutes. Must be zero or greater. |
| `status` | string | Current crowding status. Allowed values are `green`, `yellow`, and `red`. |

## Status values

- `green`: occupancy is below 50% of capacity.
- `yellow`: occupancy is from 50% through 80% of capacity.
- `red`: occupancy is above 80% of capacity.

Status values are lowercase and should be treated as an enum. This schema documents the shared response shape only; it does not create an API or connect to a cloud service.

## Reporting interval and edge input

The edge input uses the transport fields `facility_id`, `timestamp`, `occupancy`, `inflow`, and `outflow`. Lambda maps these to the response fields above and obtains `capacity` from `FACILITY_CAPACITY`. The edge MQTT message also includes `reporting_interval_seconds`, the measured duration represented by each `inflow` and `outflow` count. This is transport metadata, not part of the API response; `REPORTING_INTERVAL_SECONDS` remains a fallback for older messages without it.
