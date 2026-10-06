# Cloud Telemetry Pipeline Test

**Date:** 2026-09-17  
**Scope:** One telemetry message through the Lambda, DynamoDB, and API handlers.

## Test method

The test used the repository's real handlers with an in-memory DynamoDB-compatible double injected through `state_store`. The input was an AWS IoT-style JSON event payload. No frontend code was changed.

Sample payload:

```json
{
  "location_id": "library_01",
  "timestamp": "2026-09-17T10:30:00Z",
  "occupancy": 42,
  "capacity": 100,
  "occupancy_percentage": 42,
  "people_in": 8,
  "people_out": 5,
  "estimated_wait_minutes": 6,
  "status": "green"
}
```

## Results

| Check | Result |
| --- | --- |
| Lambda receives the telemetry payload | PASS |
| Payload validation against `docs/telemetry-schema.md` | PASS |
| Telemetry stored in DynamoDB-shaped item | PASS |
| Stored item has the expected key and fields | PASS |
| API retrieves the latest telemetry for `library_01` | PASS |
| API response matches the documented schema | PASS |
| Missing, negative, and zero-capacity inputs are rejected safely | PASS |
| Frontend modified | NO |

Stored item and API response:

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

The handler recalculates `estimated_wait_minutes` from occupancy and arrivals, so the supplied value of `6` becomes `round(42 / 8) = 5` before storage and in the API response.

Invalid payload checks returned HTTP `400` with `accepted: false` and did not create additional DynamoDB writes for:

- Missing required fields.
- Negative occupancy.
- Zero capacity.

## Environment note

This was a local handler-level integration test. AWS credentials, IoT certificates, an IoT rule, and a live DynamoDB table were not configured in the test environment, so a real AWS IoT Core-to-Lambda delivery and live DynamoDB write were not claimed as verified.

The existing `scripts/test_aws_iot.py` remains an opt-in connectivity test and requires the AWS IoT environment variables and certificate files before it can run against AWS.

## Change made during testing

`cloud/lambda/handler.py` no longer defaults missing required telemetry fields such as `capacity`, `people_in`, `people_out`, or `estimated_wait_minutes`. Incomplete messages now fail validation instead of being accepted and persisted.