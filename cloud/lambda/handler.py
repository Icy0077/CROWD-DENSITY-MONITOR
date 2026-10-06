import json
from datetime import datetime, timezone
from numbers import Real

from ..dynamodb.database import OccupancyStateStore


REQUIRED_FIELDS = (
	"location_id",
	"timestamp",
	"occupancy",
	"capacity",
	"occupancy_percentage",
	"people_in",
	"people_out",
	"estimated_wait_minutes",
	"status",
)


def _status_for_percentage(occupancy_percentage):
	if occupancy_percentage < 50:
		return "green"
	if occupancy_percentage <= 80:
		return "yellow"
	return "red"


def _normalize_timestamp(value):
	if value is None:
		return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
	if isinstance(value, datetime):
		return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
	if isinstance(value, str):
		return value.replace("+00:00", "Z") if value.endswith("+00:00") else value
	raise ValueError("timestamp must be a non-empty string")


def _normalize_telemetry(telemetry):
	if not isinstance(telemetry, dict):
		raise ValueError("Telemetry must be a JSON object")

	normalized = dict(telemetry)
	normalized["location_id"] = normalized.get("location_id", normalized.get("facility_id"))
	normalized["people_in"] = normalized.get("people_in", normalized.get("inflow"))
	normalized["people_out"] = normalized.get("people_out", normalized.get("outflow"))
	normalized["estimated_wait_minutes"] = normalized.get(
		"estimated_wait_minutes", normalized.get("wait_time")
	)
	normalized["capacity"] = normalized.get("capacity")
	if not normalized["location_id"] or not isinstance(normalized["location_id"], str):
		raise ValueError("location_id must be a non-empty string")
	if any(
		isinstance(normalized[field], bool) or not isinstance(normalized[field], Real)
		for field in ("occupancy", "people_in", "people_out", "estimated_wait_minutes", "capacity")
	):
		raise ValueError("occupancy, people_in, people_out, estimated_wait_minutes, and capacity must be numbers")
	if any(normalized[field] < 0 for field in ("occupancy", "people_in", "people_out", "estimated_wait_minutes")):
		raise ValueError("occupancy, people_in, people_out, and estimated_wait_minutes cannot be negative")
	if normalized["capacity"] <= 0:
		raise ValueError("capacity must be greater than zero")

	normalized["timestamp"] = _normalize_timestamp(normalized.get("timestamp"))
	normalized["occupancy_percentage"] = normalized.get(
		"occupancy_percentage",
		round((normalized["occupancy"] / normalized["capacity"]) * 100) if normalized["capacity"] else 0,
	)
	normalized["status"] = normalized.get("status", _status_for_percentage(normalized["occupancy_percentage"]))
	return normalized


def parse_event(event):
	if not isinstance(event, dict):
		raise ValueError("Event must be a JSON object")

	body = event.get("body")
	if body is None:
		return event
	if isinstance(body, str):
		return json.loads(body)
	if isinstance(body, dict):
		return body
	raise ValueError("Event body must be a JSON object")


def validate_telemetry(telemetry):
	normalized = _normalize_telemetry(telemetry)
	missing = [field for field in REQUIRED_FIELDS if field not in normalized]
	if missing:
		raise ValueError(f"Missing telemetry fields: {', '.join(missing)}")
	if not normalized["timestamp"] or not isinstance(normalized["timestamp"], str):
		raise ValueError("timestamp must be a non-empty string")
	if normalized["status"] not in {"green", "yellow", "red"}:
		raise ValueError("status must be green, yellow, or red")
	return normalized


def calculate_wait_time(occupancy, arrival_rate):
	if arrival_rate == 0:
		return 0
	return round(occupancy / arrival_rate)


def process_telemetry(telemetry, state_store):
	processed = validate_telemetry(telemetry)
	processed["estimated_wait_minutes"] = calculate_wait_time(
		processed["occupancy"], processed["people_in"]
	)
	processed["status"] = _status_for_percentage(processed["occupancy_percentage"])
	state_store.save_state(processed)
	return {
		"accepted": True,
		"telemetry": processed,
	}


def lambda_handler(event, context=None, state_store=None):
	try:
		telemetry = validate_telemetry(parse_event(event))
		store = state_store or OccupancyStateStore()
		response = process_telemetry(telemetry, store)
	except (TypeError, ValueError, json.JSONDecodeError) as error:
		return {
			"statusCode": 400,
			"body": json.dumps({"accepted": False, "error": str(error)}),
		}

	return {
		"statusCode": 200,
		"body": json.dumps(response),
	}
