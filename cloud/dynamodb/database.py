import os
from decimal import Decimal

import boto3


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


def _status_for_percentage(occupancy_percentage):
	if occupancy_percentage < 50:
		return "green"
	if occupancy_percentage <= 80:
		return "yellow"
	return "red"


def _to_dynamodb_value(value):
	if isinstance(value, float):
		return Decimal(str(value))
	if isinstance(value, dict):
		return {key: _to_dynamodb_value(item) for key, item in value.items()}
	if isinstance(value, list):
		return [_to_dynamodb_value(item) for item in value]
	return value


def _normalize_state(state):
	if state is None:
		return None
	state = dict(state)
	state["location_id"] = state.get("location_id", state.get("facility_id"))
	state["people_in"] = state.get("people_in", state.get("inflow", 0))
	state["people_out"] = state.get("people_out", state.get("outflow", 0))
	state["estimated_wait_minutes"] = state.get(
		"estimated_wait_minutes", state.get("wait_time", 0)
	)
	state["capacity"] = state.get("capacity", 100)
	state["capacity"] = int(state["capacity"])
	state["occupancy"] = int(state.get("occupancy", 0))
	state["people_in"] = int(state["people_in"])
	state["people_out"] = int(state["people_out"])
	state["estimated_wait_minutes"] = int(state["estimated_wait_minutes"])
	if state["capacity"] <= 0:
		raise ValueError("capacity must be greater than zero")
	state["occupancy_percentage"] = state.get(
		"occupancy_percentage",
		round((state["occupancy"] / state["capacity"]) * 100) if state["capacity"] else 0,
	)
	state["status"] = state.get("status", _status_for_percentage(state["occupancy_percentage"]))
	return state


class OccupancyStateStore:
	def __init__(self, table_name=None, region_name=None, dynamodb_resource=None):
		self.table_name = table_name or os.getenv("DYNAMODB_TABLE")
		if not self.table_name:
			raise ValueError("DYNAMODB_TABLE is required")

		resource = dynamodb_resource or boto3.resource(
			"dynamodb", region_name=region_name or os.getenv("AWS_REGION")
		)
		self.table = resource.Table(self.table_name)

	def save_state(self, state):
		normalized = _normalize_state(state)
		missing = [field for field in ("location_id", "occupancy", "timestamp") if field not in normalized]
		if missing:
			raise ValueError(f"Missing state fields: {', '.join(missing)}")

		item = {
			field: normalized[field]
			for field in STATE_FIELDS
			if field in normalized
		}
		self.table.put_item(Item=_to_dynamodb_value(item))
		return item

	def get_state(self, facility_id):
		response = self.table.get_item(Key={"location_id": facility_id})
		item = response.get("Item")
		return _normalize_state(item)
