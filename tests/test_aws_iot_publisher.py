from edge.mqtt import publisher as publisher_module


class FakeMqttClient:
	def __init__(self, client_id, protocol):
		self.client_id = client_id
		self.protocol = protocol
		self.tls_settings = None

	def tls_set(self, **settings):
		self.tls_settings = settings


def test_aws_iot_publisher_uses_environment_tls_paths(monkeypatch, tmp_path):
	certificate_paths = {}
	for name in ("AWS_IOT_CA_PATH", "AWS_IOT_CERT_PATH", "AWS_IOT_PRIVATE_KEY_PATH"):
		path = tmp_path / name
		path.write_text("test-only placeholder", encoding="ascii")
		certificate_paths[name] = str(path)

	for name, value in {
		"AWS_IOT_ENDPOINT": "example-ats.iot.us-east-1.amazonaws.com",
		"AWS_IOT_CLIENT_ID": "edge-test-device",
		"AWS_IOT_TOPIC": "cloudcrowd/telemetry",
		**certificate_paths,
		"AWS_IOT_KEEPALIVE": "45",
		"MQTT_KEEPALIVE": "5",
	}.items():
		monkeypatch.setenv(name, value)

	client = FakeMqttClient("edge-test-device", publisher_module.mqtt.MQTTv311)
	monkeypatch.setattr(publisher_module.mqtt, "Client", lambda **_kwargs: client)

	publisher = publisher_module.MqttPublisher()

	assert publisher.aws_iot_enabled is True
	assert publisher.broker == "example-ats.iot.us-east-1.amazonaws.com"
	assert publisher.port == 8883
	assert publisher.topic == "cloudcrowd/telemetry"
	assert publisher.keepalive == 45
	assert client.tls_settings == {
		"ca_certs": certificate_paths["AWS_IOT_CA_PATH"],
		"certfile": certificate_paths["AWS_IOT_CERT_PATH"],
		"keyfile": certificate_paths["AWS_IOT_PRIVATE_KEY_PATH"],
	}
