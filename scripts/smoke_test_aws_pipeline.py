"""Publish one real edge-schema message and verify the AWS pipeline end to end."""

import argparse
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import boto3
import paho.mqtt.client as mqtt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from edge.mqtt.publisher import MqttPublisher, build_telemetry


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=90, help="maximum seconds to wait for AWS propagation")
    return parser.parse_args()


def _status_for_percentage(value):
    if value < 50:
        return "green"
    if value <= 80:
        return "yellow"
    return "red"


def _expected_state(message, capacity, interval_seconds):
    percentage = round(message["occupancy"] / capacity * 100)
    arrivals_per_minute = message["inflow"] / (interval_seconds / 60)
    wait_minutes = round(message["occupancy"] / arrivals_per_minute) if arrivals_per_minute else 0
    return {
        "location_id": message["facility_id"],
        "timestamp": message["timestamp"],
        "occupancy": message["occupancy"],
        "capacity": capacity,
        "occupancy_percentage": percentage,
        "people_in": message["inflow"],
        "people_out": message["outflow"],
        "estimated_wait_minutes": wait_minutes,
        "status": _status_for_percentage(percentage),
    }


def _wait_for_state(table, expected, deadline):
    while time.monotonic() < deadline:
        response = table.get_item(Key={"location_id": expected["location_id"]})
        item = response.get("Item")
        if item and item.get("timestamp") == expected["timestamp"]:
            return item
        time.sleep(2)
    return None


def _wait_for_lambda_log(logs, log_group, marker, start_time_ms, deadline):
    while time.monotonic() < deadline:
        response = logs.filter_log_events(
            logGroupName=log_group,
            startTime=start_time_ms,
            filterPattern=f'"{marker}"',
        )
        if response.get("events"):
            return True
        time.sleep(2)
    return False


def run(timeout):
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    api_base_url = os.environ.get("API_BASE_URL")
    table_name = os.environ.get("DYNAMODB_TABLE")
    processor_name = os.environ.get("IOT_PROCESSOR_FUNCTION_NAME")
    capacity_value = os.environ.get("FACILITY_CAPACITY")
	interval_seconds = int(os.environ.get("REPORTING_INTERVAL_SECONDS", "5"))
    missing = [
        name
        for name, value in {
            "API_BASE_URL": api_base_url,
            "DYNAMODB_TABLE": table_name,
            "FACILITY_CAPACITY": capacity_value,
            "IOT_PROCESSOR_FUNCTION_NAME": processor_name,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError("Missing required smoke-test environment variables: " + ", ".join(missing))
    capacity = int(capacity_value)
    if capacity <= 0 or interval_seconds <= 0:
        raise ValueError("FACILITY_CAPACITY and REPORTING_INTERVAL_SECONDS must be greater than zero")

    facility_id = f"aws-smoke-{uuid.uuid4().hex}"
    message = build_telemetry(
        facility_id,
        occupancy=12,
        inflow=3,
        outflow=1,
    )
    expected = _expected_state(message, capacity, interval_seconds)
    publisher = MqttPublisher()
    received = threading.Event()
    connected = threading.Event()
    subscribed = threading.Event()
    receive_matches = []
    connection_results = []
    subscription_results = []

    def on_message(_client, _userdata, mqtt_message):
        if mqtt_message.topic != publisher.topic:
            return
        try:
            decoded = json.loads(mqtt_message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if decoded == message:
            receive_matches.append(decoded)
            received.set()

    def on_connect(_client, _userdata, _flags, result, *_properties):
        connection_results.append(result)
        connected.set()

    def on_subscribe(_client, _userdata, _message_id, granted_qos, *_properties):
        subscription_results.extend(granted_qos)
        subscribed.set()

    publisher.client.on_message = on_message
    publisher.client.on_connect = on_connect
    publisher.client.on_subscribe = on_subscribe
    deadline = time.monotonic() + timeout
    start_time_ms = int(time.time() * 1000)
    try:
        publisher.connect()
        if not connected.wait(max(0, deadline - time.monotonic())):
            raise TimeoutError("AWS IoT did not acknowledge the MQTT connection before timeout")
        connection_result = connection_results[0]
        if getattr(connection_result, "is_failure", connection_result != 0):
            raise RuntimeError(f"AWS IoT rejected the MQTT connection with code {connection_result}")

        result, _message_id = publisher.client.subscribe(publisher.topic, qos=publisher.qos)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT subscribe failed with code {result}")
        if not subscribed.wait(max(0, deadline - time.monotonic())):
            raise TimeoutError("AWS IoT did not acknowledge the MQTT subscription before timeout")
        if not subscription_results or any(
            getattr(qos, "is_failure", qos == 128) for qos in subscription_results
        ):
            raise RuntimeError("AWS IoT rejected the MQTT subscription")

        publisher.publish(message)
        if not received.wait(max(0, deadline - time.monotonic())):
            raise TimeoutError("AWS IoT did not return the published message on the subscribed topic")
        print("IOT_RECEIVE: PASS")
    finally:
        publisher.close()

    region = os.getenv("AWS_REGION", "ap-south-1")
    session = boto3.Session(region_name=region)
    dynamodb = session.resource("dynamodb")
    table = dynamodb.Table(table_name)
    state = _wait_for_state(table, expected, deadline)
    if state is None:
        raise TimeoutError("DynamoDB did not contain the new facility state before timeout")

    logs = session.client("logs")
    log_group = os.getenv("IOT_PROCESSOR_LOG_GROUP", f"/aws/lambda/{processor_name}")
    if not _wait_for_lambda_log(logs, log_group, facility_id, start_time_ms, deadline):
        raise TimeoutError("No Lambda processing log containing the smoke-test facility ID was found")
    print("LAMBDA_EXECUTION: PASS")
    print("DYNAMODB_UPDATE: PASS")

    api_url = f"{api_base_url.rstrip('/')}/telemetry/latest?{urlencode({'facility_id': facility_id})}"
    try:
        with urlopen(api_url, timeout=max(1, deadline - time.monotonic())) as response:
            api_state = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(f"API request failed: {error}") from error
    if api_state != expected:
        raise RuntimeError("API response did not match the telemetry state saved in DynamoDB")
    print("API_STATE_MATCH: PASS")


def main():
    args = _parse_args()
    try:
        run(args.timeout)
    except Exception as error:
        print(f"AWS_PIPELINE_SMOKE_TEST: FAIL ({type(error).__name__}: {error})")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
