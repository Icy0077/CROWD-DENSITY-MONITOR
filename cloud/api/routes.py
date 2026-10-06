import json
from datetime import datetime, timezone
from decimal import Decimal

from ..dynamodb.database import OccupancyStateStore


JSON_HEADERS = {"Content-Type": "application/json"}


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _get_facility_id(event):
    path_parameters = event.get("pathParameters") or {}
    facility_id = path_parameters.get("facility_id") or event.get("facility_id")
    if not facility_id:
        raise ValueError("facility_id is required")
    return facility_id


def _response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": JSON_HEADERS,
        "body": json.dumps(payload, default=_json_default),
    }


def _status_for_percentage(occupancy_percentage):
    if occupancy_percentage < 50:
        return "green"
    if occupancy_percentage <= 80:
        return "yellow"
    return "red"


def _mock_telemetry(location_id):
    return {
        "location_id": location_id or "library_01",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "occupancy": 42,
        "capacity": 100,
        "occupancy_percentage": 42,
        "people_in": 8,
        "people_out": 5,
        "estimated_wait_minutes": 6,
        "status": "green",
    }


def _telemetry_from_state(state, location_id):
    occupancy = int(state.get("occupancy", 0))
    capacity = int(state.get("capacity", 100))
    occupancy_percentage = state.get(
        "occupancy_percentage",
        round((occupancy / capacity) * 100) if capacity else 0,
    )
    occupancy_percentage = int(occupancy_percentage)

    return {
        "location_id": state.get("location_id", state.get("facility_id", location_id)),
        "timestamp": state.get(
            "timestamp",
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        ),
        "occupancy": occupancy,
        "capacity": capacity,
        "occupancy_percentage": occupancy_percentage,
        "people_in": int(state.get("people_in", state.get("inflow", 0))),
        "people_out": int(state.get("people_out", state.get("outflow", 0))),
        "estimated_wait_minutes": int(
            state.get("estimated_wait_minutes", state.get("wait_time", 0))
        ),
        "status": state.get("status", _status_for_percentage(occupancy_percentage)),
    }


def get_current_facility_status(event, context=None, state_store=None):
    try:
        facility_id = _get_facility_id(event)
        store = state_store or OccupancyStateStore()
        state = store.get_state(facility_id)
    except ValueError as error:
        if str(error) == "DYNAMODB_TABLE is required":
            return _response(200, _mock_telemetry(facility_id))
        return _response(400, {"error": str(error)})
    except TypeError as error:
        return _response(400, {"error": str(error)})

    if state is None:
        return _response(404, {"error": "Facility status not found"})

    return _response(200, _telemetry_from_state(state, facility_id))


def lambda_handler(event, context=None, state_store=None):
    return get_current_facility_status(event, context, state_store)
