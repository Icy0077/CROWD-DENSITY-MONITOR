import json
import os
from decimal import Decimal

from ..dynamodb.database import OccupancyStateStore, normalize_state


JSON_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
    "Access-Control-Allow-Headers": "Accept,Content-Type,Authorization",
}


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _get_facility_id(event):
    if not isinstance(event, dict):
        raise ValueError("Event must be a JSON object")
    path_parameters = event.get("pathParameters") or {}
    if not isinstance(path_parameters, dict):
        raise ValueError("pathParameters must be an object")
    query_parameters = event.get("queryStringParameters") or {}
    if not isinstance(query_parameters, dict):
        raise ValueError("queryStringParameters must be an object")
    facility_id = (
        path_parameters.get("facility_id")
        or query_parameters.get("facility_id")
        or event.get("facility_id")
        or os.getenv("DEFAULT_FACILITY_ID")
    )
    if not isinstance(facility_id, str) or not facility_id.strip():
        raise ValueError("facility_id must be a non-empty string")
    return facility_id.strip()


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


def _telemetry_from_state(state, location_id):
    state = normalize_state(state)
    if state["location_id"] != location_id:
        raise ValueError("Stored telemetry facility does not match requested facility")

    return {
        "location_id": state["location_id"] or location_id,
        "timestamp": state["timestamp"],
        "occupancy": int(state["occupancy"]),
        "capacity": int(state["capacity"]),
        "occupancy_percentage": int(state["occupancy_percentage"]),
        "people_in": int(state["people_in"]),
        "people_out": int(state["people_out"]),
        "estimated_wait_minutes": int(state["estimated_wait_minutes"]),
        "status": state["status"],
    }


def get_current_facility_status(event, context=None, state_store=None):
    if isinstance(event, dict) and (
        event.get("httpMethod") == "OPTIONS"
        or (event.get("requestContext") or {}).get("http", {}).get("method") == "OPTIONS"
    ):
        return _response(204, {})

    try:
        facility_id = _get_facility_id(event)
    except ValueError as error:
        return _response(400, {"error": str(error)})

    try:
        store = state_store if state_store is not None else OccupancyStateStore()
        state = store.get_state(facility_id)
    except ValueError as error:
        if "DYNAMODB_TABLE is required" in str(error):
            return _response(503, {"error": "Telemetry storage is not configured"})
        return _response(503, {"error": "Telemetry storage is unavailable"})
    except Exception:
        return _response(503, {"error": "Telemetry storage is unavailable"})

    if state is None:
        return _response(404, {"error": "Facility status not found"})

    try:
        return _response(200, _telemetry_from_state(state, facility_id))
    except (TypeError, ValueError, OverflowError):
        return _response(500, {"error": "Stored telemetry is invalid"})


def lambda_handler(event, context=None, state_store=None):
    return get_current_facility_status(event, context, state_store)
