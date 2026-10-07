import json
import math
import os
from datetime import datetime, timedelta, timezone
import logging
from numbers import Real

from ..dynamodb.database import (
	MAX_ARRIVAL_HISTORY_SAMPLES,
	OccupancyStateStore,
	StaleTelemetryError,
)


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
MAX_FACILITY_ID_LENGTH = 128
MAX_WAIT_MINUTES = 24 * 60
ARRIVAL_OBSERVATION_WINDOW_SECONDS = 60
MAX_STATE_UPDATE_ATTEMPTS = 5
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


def _validate_facility_id(value):
	if not isinstance(value, str):
		raise ValueError("facility_id must be a string")
	value = value.strip()
	if not value:
		raise ValueError("facility_id must be a non-empty string")
	if len(value) > MAX_FACILITY_ID_LENGTH:
		raise ValueError(f"facility_id must be at most {MAX_FACILITY_ID_LENGTH} characters")
	if any(ord(character) < 32 or ord(character) == 127 for character in value):
		raise ValueError("facility_id contains invalid control characters")
	return value


def _normalize_timestamp(value):
	if not isinstance(value, str) or not value.strip():
		raise ValueError("timestamp must be a non-empty ISO 8601 string")
	try:
		parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
	except ValueError as error:
		raise ValueError("timestamp must be a valid ISO 8601 value") from error
	if parsed.tzinfo is None or parsed.utcoffset() is None:
		raise ValueError("timestamp must include a timezone")
	return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_telemetry(telemetry):
	if not isinstance(telemetry, dict):
		raise ValueError("Telemetry must be a JSON object")

	normalized = dict(telemetry)
	edge_fields = {"facility_id", "timestamp", "occupancy", "inflow", "outflow"}
	if set(normalized) == edge_fields:
		try:
			capacity = int(os.environ["FACILITY_CAPACITY"])
		except (KeyError, TypeError, ValueError) as error:
			raise ValueError("FACILITY_CAPACITY must be configured for edge telemetry") from error
		if capacity <= 0:
			raise ValueError("FACILITY_CAPACITY must be greater than zero")
		occupancy = normalized["occupancy"]
		percentage = round((occupancy / capacity) * 100) if isinstance(occupancy, int) else None
		normalized.update(
			location_id=normalized["facility_id"],
			people_in=normalized["inflow"],
			people_out=normalized["outflow"],
			capacity=capacity,
			occupancy_percentage=percentage,
			estimated_wait_minutes=0,
			status=_status_for_percentage(percentage) if percentage is not None else None,
		)

	legacy_fields = {
		"location_id": "facility_id",
		"people_in": "inflow",
		"people_out": "outflow",
		"estimated_wait_minutes": "wait_time",
	}
	for field, legacy_field in legacy_fields.items():
		if field not in normalized and legacy_field in normalized:
			normalized[field] = normalized[legacy_field]

	allowed_fields = set(REQUIRED_FIELDS) | set(legacy_fields.values())
	unexpected = sorted(set(normalized) - allowed_fields)
	if unexpected:
		raise ValueError(f"Unexpected telemetry fields: {', '.join(unexpected)}")
	missing = [field for field in REQUIRED_FIELDS if field not in normalized]
	if missing:
		raise ValueError(f"Missing telemetry fields: {', '.join(missing)}")
	normalized["location_id"] = _validate_facility_id(normalized["location_id"])
	integer_fields = (
		"occupancy",
		"capacity",
		"people_in",
		"people_out",
	)
	if any(
		isinstance(normalized[field], bool) or not isinstance(normalized[field], int)
		for field in integer_fields
	):
		raise ValueError(f"{', '.join(integer_fields)} must be integers")
	wait_minutes = normalized["estimated_wait_minutes"]
	if (
		isinstance(wait_minutes, bool)
		or not isinstance(wait_minutes, Real)
		or not math.isfinite(float(wait_minutes))
	):
		raise ValueError("estimated_wait_minutes must be a finite number")
	if any(normalized[field] < 0 for field in ("occupancy", "people_in", "people_out", "estimated_wait_minutes")):
		raise ValueError("occupancy, people_in, people_out, and estimated_wait_minutes cannot be negative")
	if normalized["capacity"] <= 0:
		raise ValueError("capacity must be greater than zero")
	if normalized["occupancy"] > normalized["capacity"]:
		raise ValueError("occupancy cannot exceed capacity")
	percentage = normalized["occupancy_percentage"]
	if (
		isinstance(percentage, bool)
		or not isinstance(percentage, Real)
		or not math.isfinite(float(percentage))
		or percentage < 0
	):
		raise ValueError("occupancy_percentage must be a finite non-negative number")
	computed_percentage = round((normalized["occupancy"] / normalized["capacity"]) * 100)
	if percentage != computed_percentage:
		raise ValueError("occupancy_percentage does not match occupancy and capacity")
	if not isinstance(normalized["status"], str) or normalized["status"] not in {"green", "yellow", "red"}:
		raise ValueError("status must be green, yellow, or red")
	if normalized["status"] != _status_for_percentage(computed_percentage):
		raise ValueError("status does not match occupancy_percentage")
	return {
		"location_id": normalized["location_id"],
		"timestamp": _normalize_timestamp(normalized["timestamp"]),
		"occupancy": normalized["occupancy"],
		"capacity": normalized["capacity"],
		"occupancy_percentage": computed_percentage,
		"people_in": normalized["people_in"],
		"people_out": normalized["people_out"],
		"estimated_wait_minutes": normalized["estimated_wait_minutes"],
		"status": normalized["status"],
	}


def parse_event(event):
	if not isinstance(event, dict):
		raise ValueError("Event must be a JSON object")

	body = event.get("body")
	if body is None:
		return event
	if isinstance(body, bytes):
		body = body.decode("utf-8")
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


def calculate_wait_time(occupancy, people_in, reporting_interval_seconds=60):
	"""Estimate wait in minutes using Little's Law.

	``people_in`` is a count observed during ``reporting_interval_seconds``.
	It is converted to arrivals per minute before applying W = L / lambda,
	where L is occupancy in people and W is the resulting wait in minutes.
	A zero count means no arrival-rate signal is available, so the safe result
	is zero. Results are bounded to one day to prevent bad rates producing an
	unbounded dashboard value.
	"""
	if any(
		isinstance(value, bool)
		or not isinstance(value, Real)
		or not math.isfinite(float(value))
		or value < 0
		for value in (occupancy, people_in, reporting_interval_seconds)
	):
		raise ValueError("occupancy, people_in, and reporting_interval_seconds must be finite non-negative numbers")
	if reporting_interval_seconds == 0:
		raise ValueError("reporting_interval_seconds must be greater than zero")
	if people_in == 0:
		return 0
	arrival_rate_per_minute = people_in / (reporting_interval_seconds / 60)
	return min(MAX_WAIT_MINUTES, max(0.0, occupancy / arrival_rate_per_minute))


def _update_arrival_history(history, timestamp, people_in, reporting_interval_seconds):
	current_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
	window_start = current_time - timedelta(seconds=ARRIVAL_OBSERVATION_WINDOW_SECONDS)
	observations = [
		{
			"timestamp": datetime.fromisoformat(sample["timestamp"].replace("Z", "+00:00")),
			"people_in": sample["people_in"],
		}
		for sample in history
	]
	observations.append({"timestamp": current_time, "people_in": people_in})

	prior_observations = [sample for sample in observations if sample["timestamp"] <= window_start]
	window_observations = [sample for sample in observations if sample["timestamp"] > window_start]
	baseline = max(prior_observations, key=lambda sample: sample["timestamp"]) if prior_observations else None
	retained = ([baseline] if baseline else []) + window_observations
	if len(retained) > MAX_ARRIVAL_HISTORY_SAMPLES:
		raise ValueError("Arrival history exceeds the supported reporting frequency")

	has_full_window = baseline is not None
	checkpoints = ([baseline] if baseline else []) + window_observations
	max_gap = max(reporting_interval_seconds * 2, reporting_interval_seconds + 5)
	if any(
		(checkpoints[index + 1]["timestamp"] - checkpoints[index]["timestamp"]).total_seconds() > max_gap
		for index in range(len(checkpoints) - 1)
	):
		has_full_window = False

	persisted_history = [
		{
			"timestamp": sample["timestamp"].astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
			"people_in": sample["people_in"],
		}
		for sample in retained
	]
	arrivals_in_window = sum(sample["people_in"] for sample in window_observations)
	return persisted_history, arrivals_in_window, has_full_window


def _configured_reporting_interval():
	value = os.getenv("REPORTING_INTERVAL_SECONDS", "60")
	try:
		interval = float(value)
	except (TypeError, ValueError) as error:
		raise ValueError("REPORTING_INTERVAL_SECONDS must be a positive number") from error
	if not math.isfinite(interval) or interval <= 0:
		raise ValueError("REPORTING_INTERVAL_SECONDS must be a positive number")
	return interval


def process_telemetry(telemetry, state_store, reporting_interval_seconds=None):
	processed = validate_telemetry(telemetry)
	if reporting_interval_seconds is None:
		reporting_interval_seconds = _configured_reporting_interval()
	processed["status"] = _status_for_percentage(processed["occupancy_percentage"])
	for attempt in range(MAX_STATE_UPDATE_ATTEMPTS):
		previous_timestamp, history = state_store.get_arrival_history(processed["location_id"])
		if previous_timestamp is not None and (
			datetime.fromisoformat(processed["timestamp"].replace("Z", "+00:00"))
			<= datetime.fromisoformat(previous_timestamp.replace("Z", "+00:00"))
		):
			raise StaleTelemetryError("telemetry timestamp is not newer than stored state")
		history, arrivals_in_window, has_full_window = _update_arrival_history(
			history,
			processed["timestamp"],
			processed["people_in"],
			reporting_interval_seconds,
		)
		processed["estimated_wait_minutes"] = (
			calculate_wait_time(
				processed["occupancy"],
				arrivals_in_window,
				reporting_interval_seconds=ARRIVAL_OBSERVATION_WINDOW_SECONDS,
			)
			if has_full_window
			else 0
		)
		try:
			state_store.save_state(
				processed,
				arrival_history=history,
				expected_timestamp=previous_timestamp,
			)
			break
		except StaleTelemetryError:
			if attempt == MAX_STATE_UPDATE_ATTEMPTS - 1:
				raise RuntimeError("Unable to update rolling arrival history after concurrent writes")
	LOGGER.info(
		"Processed telemetry location_id=%s timestamp=%s",
		processed["location_id"],
		processed["timestamp"],
	)
	return {
		"accepted": True,
		"telemetry": processed,
	}


def lambda_handler(event, context=None, state_store=None):
	try:
		telemetry = validate_telemetry(parse_event(event))
	except (TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
		return {
			"statusCode": 400,
			"body": json.dumps({"accepted": False, "error": str(error)}),
		}

	try:
		store = state_store if state_store is not None else OccupancyStateStore()
		response = process_telemetry(telemetry, store)
	except StaleTelemetryError:
		return {
			"statusCode": 202,
			"body": json.dumps({"accepted": False, "error": "Telemetry timestamp is older than stored state"}),
		}
	except Exception:
		return {
			"statusCode": 500,
			"body": json.dumps({"accepted": False, "error": "Unable to process telemetry"}),
		}

	return {
		"statusCode": 200,
		"body": json.dumps(response),
	}
