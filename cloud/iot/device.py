import json
import os
import ssl

import paho.mqtt.client as mqtt


class AwsIotDevice:
	def __init__(self):
		self.endpoint = os.getenv("AWS_IOT_ENDPOINT")
		self.port = int(os.getenv("AWS_IOT_PORT", "8883"))
		self.client_id = os.getenv("AWS_IOT_CLIENT_ID")
		self.root_ca = os.getenv("AWS_IOT_ROOT_CA")
		self.certificate = os.getenv("AWS_IOT_CERTIFICATE")
		self.private_key = os.getenv("AWS_IOT_PRIVATE_KEY")
		self.topic = os.getenv("AWS_IOT_TOPIC", "cloudcrowd/telemetry")
		self.keepalive = int(os.getenv("AWS_IOT_KEEPALIVE", "60"))
		self.client = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv311)
		self._connected = False

	def _validate_configuration(self):
		missing = [
			name
			for name, value in (
				("AWS_IOT_ENDPOINT", self.endpoint),
				("AWS_IOT_CLIENT_ID", self.client_id),
				("AWS_IOT_ROOT_CA", self.root_ca),
				("AWS_IOT_CERTIFICATE", self.certificate),
				("AWS_IOT_PRIVATE_KEY", self.private_key),
			)
			if not value
		]
		if missing:
			raise RuntimeError(f"Missing AWS IoT configuration: {', '.join(missing)}")

	def connect(self):
		if self._connected:
			return

		self._validate_configuration()
		self.client.tls_set(
			ca_certs=self.root_ca,
			certfile=self.certificate,
			keyfile=self.private_key,
			tls_version=ssl.PROTOCOL_TLS_CLIENT,
		)
		self.client.connect(self.endpoint, self.port, self.keepalive)
		self.client.loop_start()
		self._connected = True

	def publish(self, telemetry, topic=None):
		self.connect()
		message = self.client.publish(topic or self.topic, json.dumps(telemetry), qos=1)
		message.wait_for_publish()
		if message.rc != mqtt.MQTT_ERR_SUCCESS:
			raise RuntimeError(f"AWS IoT publish failed with code {message.rc}")

	def subscribe(self, callback, topic=None, qos=1):
		self.connect()
		subscription = topic or self.topic
		self.client.message_callback_add(subscription, callback)
		result, message_id = self.client.subscribe(subscription, qos=qos)
		if result != mqtt.MQTT_ERR_SUCCESS:
			raise RuntimeError(f"AWS IoT subscribe failed with code {result}")
		return message_id

	def close(self):
		if self._connected:
			self.client.disconnect()
			self.client.loop_stop()
			self._connected = False
