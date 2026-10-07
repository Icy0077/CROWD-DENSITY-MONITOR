import os
import math
from datetime import datetime, timezone
from decimal import Decimal
from numbers import Real

import boto3
from botocore.exceptions import ClientError


STATE_FIELDS = (
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
ARRIVAL_HISTORY_FIELD = "arrival_history"
MAX_ARRIVAL_HISTORY_SAMPLES = 120
MAX_FACILITY_ID_LENGTH = 128


class StaleTelemetryError(Exception):
	"""Raised when an older telemetry record would replace newer state."""


def _status_for_percentage(occupancy_percentage):
	if occupancy_percentage < 50:
		return "green"
	if occupancy_percentage <= 80:
		return "yellow"
	return "red"


def _validate_facility_id(value):
	if not isinstance(value, str):
		raise ValueError("location_id must be a string")
	value = value.strip()
	if not value:
		raise ValueError("location_id must be a non-empty string")
	if len(value) > MAX_FACILITY_ID_LENGTH:
		raise ValueError(f"location_id must be at most {MAX_FACILITY_ID_LENGTH} characters")
	if any(ord(character) < 32 or ord(character) == 127 for character in value):
		raise ValueError("location_id contains invalid control characters")
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


def _to_dynamodb_value(value):
	if isinstance(value, float):
		return Decimal(str(value))
	if isinstance(value, dict):
		return {key: _to_dynamodb_value(item) for key, item in value.items()}
	if isinstance(value, list):
		return [_to_dynamodb_value(item) for item in value]
	return value


def normalize_state(state):
	if state is None:
		return None
	if not isinstance(state, dict):
		raise ValueError("State must be an object")
	state = dict(state)
	for field, legacy_field in {
		"location_id": "facility_id",
		"people_in": "inflow",
		"people_out": "outflow",
		"estimated_wait_minutes": "wait_time",
	}.items():
		if field not in state and legacy_field in state:
			state[field] = state[legacy_field]

	missing = [field for field in STATE_FIELDS if field not in state]
	if missing:
		raise ValueError(f"Missing state fields: {', '.join(missing)}")
	state["location_id"] = _validate_facility_id(state["location_id"])
	state["timestamp"] = _normalize_timestamp(state["timestamp"])
	integer_fields = ("occupancy", "capacity", "people_in", "people_out")
	for field in integer_fields:
		value = state[field]
		if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
			raise ValueError(f"{field} must be an integer")
		try:
			integer_value = int(value)
			finite_value = math.isfinite(float(value))
		except (OverflowError, ValueError):
			raise ValueError(f"{field} must be a finite integer") from None
		if not finite_value or integer_value != value:
			raise ValueError(f"{field} must be a finite integer")
		state[field] = integer_value
	wait_minutes = state["estimated_wait_minutes"]
	if (
		isinstance(wait_minutes, bool)
		or not isinstance(wait_minutes, (Real, Decimal))
		or not math.isfinite(float(wait_minutes))
		or wait_minutes < 0
	):
		raise ValueError("estimated_wait_minutes must be a finite non-negative number")
	if any(state[field] < 0 for field in ("occupancy", "people_in", "people_out")):
		raise ValueError("occupancy and counts cannot be negative")
	if state["capacity"] <= 0:
		raise ValueError("capacity must be greater than zero")
	if state["occupancy"] > state["capacity"]:
		raise ValueError("occupancy cannot exceed capacity")
	percentage = state["occupancy_percentage"]
	if (
		isinstance(percentage, bool)
		or not isinstance(percentage, (Real, Decimal))
		or not math.isfinite(float(percentage))
		or percentage != round((state["occupancy"] / state["capacity"]) * 100)
	):
		raise ValueError("occupancy_percentage does not match occupancy and capacity")
	state["occupancy_percentage"] = round((state["occupancy"] / state["capacity"]) * 100)
	expected_status = _status_for_percentage(state["occupancy_percentage"])
	if state["status"] != expected_status:
		raise ValueError("status does not match occupancy_percentage")
	return {field: state[field] for field in STATE_FIELDS}


_normalize_state = normalize_state


class OccupancyStateStore:
	def __init__(self, table_name=None, region_name=None, dynamodb_resource=None):
		self.table_name = table_name or os.getenv("DYNAMODB_TABLE")
		if not self.table_name:
			raise ValueError("DYNAMODB_TABLE is required")

		resource = dynamodb_resource or boto3.resource(
			"dynamodb", region_name=region_name or os.getenv("AWS_REGION")
		)
		self.table = resource.Table(self.table_name)

	def save_state(self, state, arrival_history=None, expected_timestamp=None):
		normalized = normalize_state(state)
		item = {
			field: normalized[field]
			for field in STATE_FIELDS
			if field in normalized
		}
		if arrival_history is not None:
			item[ARRIVAL_HISTORY_FIELD] = _normalize_arrival_history(arrival_history)
		try:
			if arrival_history is None:
				self.table.put_item(
					Item=_to_dynamodb_value(item),
					ConditionExpression="attribute_not_exists(#location_id) OR #timestamp <= :timestamp",
					ExpressionAttributeNames={"#location_id": "location_id", "#timestamp": "timestamp"},
					ExpressionAttributeValues={":timestamp": item["timestamp"]},
				)
			elif expected_timestamp is None:
				self.table.put_item(
					Item=_to_dynamodb_value(item),
					ConditionExpression="attribute_not_exists(#location_id)",
					ExpressionAttributeNames={"#location_id": "location_id"},
				)
			else:
				self.table.put_item(
					Item=_to_dynamodb_value(item),
					ConditionExpression="#timestamp = :expected_timestamp",
					ExpressionAttributeNames={"#timestamp": "timestamp"},
					ExpressionAttributeValues={
						":expected_timestamp": expected_timestamp,
					},
				)
		except ClientError as error:
			if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
				raise StaleTelemetryError("telemetry timestamp is older than stored state") from error
			raise
		return item

	def get_arrival_history(self, facility_id):
		facility_id = _validate_facility_id(facility_id)
		response = self.table.get_item(Key={"location_id": facility_id}, ConsistentRead=True)
		item = response.get("Item")
		if item is None:
			return None, []
		return (
			_normalize_timestamp(item["timestamp"]),
			_normalize_arrival_history(item.get(ARRIVAL_HISTORY_FIELD, [])),
		)

	def get_state(self, facility_id):
		facility_id = _validate_facility_id(facility_id)
		response = self.table.get_item(Key={"location_id": facility_id}, ConsistentRead=True)
		item = response.get("Item")
		return normalize_state(item)


def _normalize_arrival_history(history):
	if not isinstance(history, list) or len(history) > MAX_ARRIVAL_HISTORY_SAMPLES:
		raise ValueError("arrival_history must be a bounded list")
	normalized = []
	for sample in history:
		if not isinstance(sample, dict) or set(sample) != {"timestamp", "people_in"}:
			raise ValueError("arrival_history contains an invalid sample")
		people_in = sample["people_in"]
		if isinstance(people_in, bool) or not isinstance(people_in, (Real, Decimal)):
			raise ValueError("arrival_history people_in must be a non-negative integer")
		try:
			integer_value = int(people_in)
			finite_value = math.isfinite(float(people_in))
		except (OverflowError, ValueError):
			raise ValueError("arrival_history people_in must be a non-negative integer") from None
		if not finite_value or integer_value != people_in or integer_value < 0:
			raise ValueError("arrival_history people_in must be a non-negative integer")
		normalized.append({
			"timestamp": _normalize_timestamp(sample["timestamp"]),
			"people_in": integer_value,
		})
	parsed_timestamps = [
		datetime.fromisoformat(sample["timestamp"].replace("Z", "+00:00"))
		for sample in normalized
	]
	if any(parsed_timestamps[index] >= parsed_timestamps[index + 1] for index in range(len(parsed_timestamps) - 1)):
		raise ValueError("arrival_history timestamps must be strictly increasing")
	return normalized
