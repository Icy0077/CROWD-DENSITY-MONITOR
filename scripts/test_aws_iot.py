"""Opt-in AWS IoT Core MQTT connectivity test."""

import argparse
import json
import os
from pathlib import Path
import socket
import sys
import threading

import paho.mqtt.client as mqtt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from edge.mqtt.publisher import MqttPublisher, build_telemetry


AWS_CONFIG_VARS = (
    "AWS_IOT_ENDPOINT",
    "AWS_IOT_CLIENT_ID",
    "AWS_IOT_TOPIC",
    "AWS_IOT_CA_PATH",
    "AWS_IOT_CERT_PATH",
    "AWS_IOT_PRIVATE_KEY_PATH",
)


def _parse_args():
    parser = argparse.ArgumentParser(description="Test one AWS IoT Core MQTT telemetry round trip.")
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Seconds to wait for connection and message receipt (default: 10).",
    )
    return parser.parse_args()


def _require_aws_configuration():
    if not any(os.getenv(name) for name in AWS_CONFIG_VARS):
        raise ValueError("AWS IoT configuration is not set in the environment or .env")


def _connect_with_timeout(publisher, timeout):
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        publisher.connect()
    finally:
        socket.setdefaulttimeout(previous_timeout)


def run_test(timeout):
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    _require_aws_configuration()
    publisher = MqttPublisher()
    received = threading.Event()
    expected_payload = build_telemetry(
        "aws_iot_connection_test",
        occupancy=0,
        people_in=0,
        people_out=0,
        capacity=100,
    )
    received_payload = []

    def on_message(_client, _userdata, message):
        if message.topic != publisher.topic:
            return
        try:
            candidate = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if candidate == expected_payload:
            received_payload.append(candidate)
            received.set()

    publisher.client.on_message = on_message
    try:
        _connect_with_timeout(publisher, timeout)
        print("CONNECTION: PASS")

        subscribe_result, _message_id = publisher.client.subscribe(publisher.topic, qos=publisher.qos)
        if subscribe_result != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT subscribe failed with code {subscribe_result}")
        print("SUBSCRIBE: PASS")

        publisher.publish(expected_payload)
        print("PUBLISH: PASS")

        if not received.wait(timeout):
            raise TimeoutError("timed out waiting for the test telemetry message")
        print("MESSAGE_RECEIVE: PASS")
    finally:
        publisher.close()


def main():
    args = _parse_args()
    try:
        run_test(args.timeout)
    except (FileNotFoundError, ValueError) as exc:
        print(f"CONFIGURATION_ERROR: {exc}")
        return 1
    except (ConnectionError, OSError, socket.timeout, TimeoutError) as exc:
        print(f"CONNECTION_ERROR: {exc}")
        return 1
    except Exception as exc:
        print(f"MQTT_TEST_ERROR: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
