import json
import logging
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from importlib import import_module

import pytest
from botocore.exceptions import ClientError

from cloud.api.routes import get_current_facility_status
from cloud.dynamodb.database import OccupancyStateStore


lambda_module = import_module("cloud.lambda.handler")
calculate_wait_time = lambda_module.calculate_wait_time
lambda_handler = lambda_module.lambda_handler
validate_telemetry = lambda_module.validate_telemetry


@pytest.fixture(autouse=True)
def lambda_reporting_interval(monkeypatch):
	# Keep Lambda unit tests explicit while the local edge default is five seconds.
	monkeypatch.setenv("REPORTING_INTERVAL_SECONDS", "60")


VALID_TELEMETRY = {
	"location_id": "library_01",
	"timestamp": "2026-09-17T10:30:00Z",
	"occupancy": 42,
	"capacity": 100,
	"occupancy_percentage": 42,
	"people_in": 8,
	"people_out": 5,
	"estimated_wait_minutes": 0,
	"status": "green",
}


class MemoryTable:
	def __init__(self):
		self.items = {}
		self.put_calls = 0

	def put_item(self, Item, **kwargs):
		existing = self.items.get(Item["location_id"])
		expression_values = kwargs.get("ExpressionAttributeValues", {})
		expected_timestamp = expression_values.get(":expected_timestamp")
		if expected_timestamp is not None and (
			existing is None
			or existing["timestamp"] != expected_timestamp
			or existing["timestamp"] >= Item["timestamp"]
		):
			raise ClientError(
				{"Error": {"Code": "ConditionalCheckFailedException", "Message": "concurrent write"}},
				"PutItem",
			)
		if kwargs.get("ConditionExpression") == "attribute_not_exists(#location_id)" and existing is not None:
			raise ClientError(
				{"Error": {"Code": "ConditionalCheckFailedException", "Message": "already exists"}},
				"PutItem",
			)
		if expected_timestamp is None and existing and existing["timestamp"] > Item["timestamp"]:
			raise ClientError(
				{"Error": {"Code": "ConditionalCheckFailedException", "Message": "stale"}},
				"PutItem",
			)
		self.items[Item["location_id"]] = dict(Item)
		self.put_calls += 1
		return {"ResponseMetadata": {"HTTPStatusCode": 200}}

	def get_item(self, Key, **_kwargs):
		item = self.items.get(Key["location_id"])
		return {"Item": dict(item)} if item is not None else {}


class MemoryDynamoResource:
	def __init__(self):
		self.tables = {}

	def Table(self, table_name):
		return self.tables.setdefault(table_name, MemoryTable())


def make_store():
	resource = MemoryDynamoResource()
	store = OccupancyStateStore(
		table_name="telemetry",
		dynamodb_resource=resource,
	)
	return store, resource.tables["telemetry"]


def submit_reading(store, seconds, people_in, occupancy=42):
	timestamp = (
		datetime(2026, 9, 17, 10, 30, tzinfo=timezone.utc) + timedelta(seconds=seconds)
	).isoformat().replace("+00:00", "Z")
	telemetry = {
		**VALID_TELEMETRY,
		"timestamp": timestamp,
		"occupancy": occupancy,
		"occupancy_percentage": occupancy,
		"people_in": people_in,
		"status": "green",
	}
	response = lambda_handler(telemetry, state_store=store)
	assert response["statusCode"] == 200
	return json.loads(response["body"])["telemetry"]["estimated_wait_minutes"]


def test_valid_mqtt_telemetry_is_validated_and_processed():
	store, _ = make_store()
	message = json.dumps(VALID_TELEMETRY)

	response = lambda_handler({"body": message}, state_store=store)

	assert response["statusCode"] == 200
	result = json.loads(response["body"])
	assert result["accepted"] is True
	assert result["telemetry"]["estimated_wait_minutes"] == 0
	assert validate_telemetry(VALID_TELEMETRY)["location_id"] == "library_01"


def test_processing_log_includes_facility_id(caplog):
	store, _ = make_store()
	telemetry = {**VALID_TELEMETRY, "location_id": "aws-smoke-regression"}

	with caplog.at_level(logging.INFO):
		response = lambda_handler(telemetry, state_store=store)

	assert response["statusCode"] == 200
	assert any("location_id=aws-smoke-regression" in record.message for record in caplog.records)


def test_edge_telemetry_is_normalized_using_deployment_configuration(monkeypatch):
	monkeypatch.setenv("FACILITY_CAPACITY", "100")
	monkeypatch.setenv("REPORTING_INTERVAL_SECONDS", "120")
	store, _ = make_store()
	edge_message = {
		"facility_id": "library_01",
		"timestamp": "2026-09-17T10:30:00Z",
		"occupancy": 42,
		"inflow": 8,
		"outflow": 5,
	}

	response = lambda_handler(edge_message, state_store=store)

	assert response["statusCode"] == 200
	payload = json.loads(response["body"])["telemetry"]
	assert payload["location_id"] == "library_01"
	assert payload["people_in"] == 8
	assert payload["people_out"] == 5
	assert payload["capacity"] == 100
	assert payload["estimated_wait_minutes"] == 0


def test_edge_telemetry_requires_configured_facility_capacity(monkeypatch):
	monkeypatch.delenv("FACILITY_CAPACITY", raising=False)
	edge_message = {
		"facility_id": "library_01",
		"timestamp": "2026-09-17T10:30:00Z",
		"occupancy": 42,
		"inflow": 8,
		"outflow": 5,
	}

	with pytest.raises(ValueError, match="FACILITY_CAPACITY"):
		validate_telemetry(edge_message)


@pytest.mark.parametrize(
	("field", "value"),
	[
		("capacity", None),
		("occupancy", -1),
		("occupancy_over_capacity", 101),
		("people_in", 1.5),
		("timestamp", "not-a-timestamp"),
		("status", "purple"),
		("occupancy_percentage", 99),
		("image_data", "should-not-be-accepted"),
	],
)
def test_invalid_telemetry_is_rejected_without_state_write(field, value):
	store, table = make_store()
	telemetry = deepcopy(VALID_TELEMETRY)
	if field == "occupancy_over_capacity":
		telemetry["occupancy"] = value
	else:
		telemetry[field] = value
		if value is None:
			del telemetry[field]
	if field == "occupancy_over_capacity":
		telemetry["occupancy_percentage"] = 101

	response = lambda_handler({"body": json.dumps(telemetry)}, state_store=store)

	assert response["statusCode"] == 400
	assert json.loads(response["body"])["accepted"] is False
	assert table.put_calls == 0


def test_wait_time_uses_littles_law_with_explicit_interval_units():
	assert calculate_wait_time(42, 8, reporting_interval_seconds=60) == 5.25
	assert calculate_wait_time(42, 8, reporting_interval_seconds=120) == 10.5
	assert calculate_wait_time(42, 0, reporting_interval_seconds=60) == 0
	with pytest.raises(ValueError):
		calculate_wait_time(-1, 8)
	with pytest.raises(ValueError):
		calculate_wait_time(42, 8, reporting_interval_seconds=0)
	assert calculate_wait_time(100000, 1, reporting_interval_seconds=1) == 24 * 60


@pytest.mark.parametrize(
	("occupancy", "arrivals", "expected"),
	[(2, 5, 0.4), (4, 5, 0.8), (7, 5, 1.4), (28, 5, 5.6)],
)
def test_fractional_wait_precision_survives_calculation_storage_and_api(occupancy, arrivals, expected):
	store, table = make_store()
	submit_reading(store, 0, people_in=0, occupancy=occupancy)
	response = lambda_handler(
		{
			**VALID_TELEMETRY,
			"timestamp": "2026-09-17T10:31:00Z",
			"occupancy": occupancy,
			"occupancy_percentage": occupancy,
			"people_in": arrivals,
			"status": "green",
		},
		state_store=store,
	)

	assert response["statusCode"] == 200
	processed = json.loads(response["body"])["telemetry"]
	assert processed["estimated_wait_minutes"] == pytest.approx(expected)
	assert float(table.items["library_01"]["estimated_wait_minutes"]) == pytest.approx(expected)

	api_response = get_current_facility_status(
		{"queryStringParameters": {"facility_id": "library_01"}},
		state_store=store,
	)
	api_value = json.loads(api_response["body"])["estimated_wait_minutes"]
	assert isinstance(api_value, (int, float))
	assert api_value == pytest.approx(expected)


def test_rolling_wait_estimate_uses_arrivals_from_the_full_sixty_second_window():
	store, _ = make_store()
	estimate = 0
	for seconds in range(0, 61, 5):
		estimate = submit_reading(store, seconds, people_in=1 if seconds == 5 else 0)

	assert estimate == 42


def test_rolling_wait_estimate_handles_one_arrival_over_sixty_seconds():
	store, _ = make_store()
	submit_reading(store, 0, people_in=0)

	assert submit_reading(store, 60, people_in=1) == 42


def test_rolling_wait_estimate_sums_multiple_arrivals_in_sixty_seconds():
	store, _ = make_store()
	submit_reading(store, 0, people_in=0)
	submit_reading(store, 20, people_in=2)
	submit_reading(store, 40, people_in=3)

	assert submit_reading(store, 60, people_in=1) == 7


def test_rolling_wait_estimate_is_zero_when_full_window_has_no_arrivals():
	store, _ = make_store()
	for seconds in range(0, 61, 5):
		estimate = submit_reading(store, seconds, people_in=0)

	assert estimate == 0


def test_rolling_wait_estimate_is_zero_when_occupancy_is_zero():
	store, _ = make_store()
	submit_reading(store, 0, people_in=0, occupancy=0)
	submit_reading(store, 30, people_in=3, occupancy=0)

	assert submit_reading(store, 60, people_in=3, occupancy=0) == 0


def test_rolling_wait_estimate_is_zero_until_history_covers_the_window():
	store, _ = make_store()
	submit_reading(store, 5, people_in=1)

	assert submit_reading(store, 10, people_in=0) == 0


def test_rolling_wait_estimate_expires_arrivals_outside_the_window():
	store, _ = make_store()
	submit_reading(store, 0, people_in=0)
	submit_reading(store, 5, people_in=5)
	assert submit_reading(store, 60, people_in=0) == pytest.approx(8.4)

	assert submit_reading(store, 65, people_in=0) == 0


def test_invalid_reporting_interval_configuration_is_rejected(monkeypatch):
	monkeypatch.setenv("REPORTING_INTERVAL_SECONDS", "not-a-number")
	store, table = make_store()
	response = lambda_handler(VALID_TELEMETRY, state_store=store)

	assert response["statusCode"] == 500
	assert table.put_calls == 0


def test_older_telemetry_cannot_replace_latest_state():
	store, table = make_store()
	newer = {**VALID_TELEMETRY, "timestamp": "2026-09-17T10:31:00Z"}
	store.save_state(newer)

	response = lambda_handler(VALID_TELEMETRY, state_store=store)

	assert response["statusCode"] == 202
	assert table.items["library_01"]["timestamp"] == "2026-09-17T10:31:00Z"


def test_state_save_and_retrieval_use_injected_dynamodb_resource():
	store, table = make_store()
	store.save_state(VALID_TELEMETRY)

	assert table.items["library_01"]["occupancy"] == 42
	assert store.get_state("library_01")["people_in"] == 8
	assert store.get_state("unknown") is None


def test_api_response_matches_frontend_telemetry_contract():
	store, _ = make_store()
	response = lambda_handler(
		{"body": json.dumps(VALID_TELEMETRY)},
		state_store=store,
	)
	assert response["statusCode"] == 200

	api_response = get_current_facility_status(
		{"queryStringParameters": {"facility_id": "library_01"}},
		state_store=store,
	)

	assert api_response["statusCode"] == 200
	payload = json.loads(api_response["body"])
	assert set(payload) == set(VALID_TELEMETRY)
	assert payload["estimated_wait_minutes"] == 0
	assert payload["occupancy"] == 42


def test_api_uses_configured_default_facility_for_frontend_request(monkeypatch):
	store, _ = make_store()
	store.save_state({**VALID_TELEMETRY, "estimated_wait_minutes": 5})
	monkeypatch.setenv("DEFAULT_FACILITY_ID", "library_01")

	response = get_current_facility_status({}, state_store=store)

	assert response["statusCode"] == 200
	assert json.loads(response["body"])["location_id"] == "library_01"


def test_api_returns_not_found_for_unknown_facility():
	store, _ = make_store()
	response = get_current_facility_status(
		{"queryStringParameters": {"facility_id": "unknown"}},
		state_store=store,
	)

	assert response["statusCode"] == 404
	assert json.loads(response["body"]) == {"error": "Facility status not found"}


def test_api_handles_options_and_invalid_stored_state():
	options = get_current_facility_status({"httpMethod": "OPTIONS"})
	assert options["statusCode"] == 204

	class InvalidStateStore:
		def get_state(self, _facility_id):
			return {"location_id": "library_01"}

	response = get_current_facility_status(
		{"queryStringParameters": {"facility_id": "library_01"}},
		state_store=InvalidStateStore(),
	)

	assert response["statusCode"] == 500
	assert json.loads(response["body"]) == {"error": "Stored telemetry is invalid"}


def test_error_handling_returns_client_and_storage_errors(monkeypatch):
	store, _ = make_store()
	bad_json = lambda_handler({"body": "{"}, state_store=store)
	assert bad_json["statusCode"] == 400

	class FailingStore:
		def save_state(self, state):
			raise RuntimeError("storage failure")

	storage_failure = lambda_handler(VALID_TELEMETRY, state_store=FailingStore())
	assert storage_failure["statusCode"] == 500
	assert "storage failure" not in storage_failure["body"]

	monkeypatch.delenv("DYNAMODB_TABLE", raising=False)
	unconfigured_api = get_current_facility_status(
		{"pathParameters": {"facility_id": "library_01"}}
	)
	assert unconfigured_api["statusCode"] == 503
	assert "occupancy" not in unconfigured_api["body"]
