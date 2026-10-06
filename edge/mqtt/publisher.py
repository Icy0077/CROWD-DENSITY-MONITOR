from datetime import datetime, timezone
import json
import os
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv


load_dotenv()

AWS_IOT_CONFIG_VARS = (
	"AWS_IOT_ENDPOINT",
	"AWS_IOT_CLIENT_ID",
	"AWS_IOT_TOPIC",
	"AWS_IOT_CA_PATH",
	"AWS_IOT_CERT_PATH",
	"AWS_IOT_PRIVATE_KEY_PATH",
)


def _status_for_percentage(occupancy_percentage):
	if occupancy_percentage < 50:
		return "green"
	if occupancy_percentage <= 80:
		return "yellow"
	return "red"


def _normalize_timestamp(value=None):
	if value is None:
		value = datetime.now(timezone.utc)
	if isinstance(value, datetime):
		return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
	if isinstance(value, str):
		return value.replace("+00:00", "Z") if value.endswith("+00:00") else value
	raise ValueError("timestamp must be a datetime or ISO 8601 string")


def build_telemetry(location_id, occupancy, people_in, people_out, timestamp=None, capacity=100):
	capacity = int(capacity or 100)
	occupancy = int(occupancy)
	people_in = int(people_in)
	people_out = int(people_out)
	occupancy_percentage = round((occupancy / capacity) * 100) if capacity else 0
	return {
		"location_id": location_id,
		"timestamp": _normalize_timestamp(timestamp),
		"occupancy": occupancy,
		"capacity": capacity,
		"occupancy_percentage": occupancy_percentage,
		"people_in": people_in,
		"people_out": people_out,
		"estimated_wait_minutes": 0,
		"status": _status_for_percentage(occupancy_percentage),
	}


class MqttPublisher:
	def __init__(self):
		self.aws_iot_enabled = any(os.getenv(name) for name in AWS_IOT_CONFIG_VARS)
		if self.aws_iot_enabled:
			self._validate_aws_iot_config()
			self.broker = os.environ["AWS_IOT_ENDPOINT"]
			self.port = int(os.getenv("AWS_IOT_PORT", "8883"))
			self.topic = os.environ["AWS_IOT_TOPIC"]
			self.client_id = os.environ["AWS_IOT_CLIENT_ID"]
		else:
			self.broker = os.getenv("MQTT_BROKER", "localhost")
			self.port = int(os.getenv("MQTT_PORT", "1883"))
			self.topic = os.getenv("MQTT_TOPIC", "cloudcrowd/telemetry")
			self.client_id = os.getenv("MQTT_CLIENT_ID") or None
		self.username = os.getenv("MQTT_USERNAME")
		self.password = os.getenv("MQTT_PASSWORD")
		self.keepalive = int(os.getenv("MQTT_KEEPALIVE", "60"))
		self.qos = int(os.getenv("MQTT_QOS", "1"))
		self.retain = os.getenv("MQTT_RETAIN", "false").lower() == "true"
		self.use_tls = self.aws_iot_enabled or os.getenv("MQTT_TLS", "false").lower() == "true"
		self.client = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv311)
		self._connected = False

		if self.aws_iot_enabled:
			self.client.tls_set(
				ca_certs=os.environ["AWS_IOT_CA_PATH"],
				certfile=os.environ["AWS_IOT_CERT_PATH"],
				keyfile=os.environ["AWS_IOT_PRIVATE_KEY_PATH"],
			)
		elif self.username:
			self.client.username_pw_set(self.username, self.password)
		elif self.use_tls:
			self.client.tls_set()

	@staticmethod
	def _validate_aws_iot_config():
		missing = [name for name in AWS_IOT_CONFIG_VARS if not os.getenv(name)]
		if missing:
			raise ValueError(
				"AWS IoT configuration is incomplete; missing: " + ", ".join(missing)
			)

		for name in ("AWS_IOT_CA_PATH", "AWS_IOT_CERT_PATH", "AWS_IOT_PRIVATE_KEY_PATH"):
			path = Path(os.environ[name])
			if not path.is_file():
				raise FileNotFoundError(
					f"AWS IoT certificate file for {name} was not found: {path}"
				)

	def connect(self):
		if self._connected:
			return

		self.client.connect(self.broker, self.port, self.keepalive)
		self.client.loop_start()
		self._connected = True

	def publish(self, telemetry):
		self.connect()
		message = self.client.publish(
			self.topic,
			json.dumps(telemetry),
			qos=self.qos,
			retain=self.retain,
		)
		message.wait_for_publish()
		if message.rc != mqtt.MQTT_ERR_SUCCESS:
			raise RuntimeError(f"MQTT publish failed with code {message.rc}")

	def close(self):
		if self._connected:
			self.client.disconnect()
			self.client.loop_stop()
			self._connected = False
