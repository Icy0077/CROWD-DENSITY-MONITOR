# MQTT telemetry publishing test

Date: 2026-09-17

## Scope

This test covers the existing publisher in `edge/mqtt/publisher.py` without connecting to AWS IoT and without using AWS credentials or certificates.

The test validates:

- telemetry JSON encoding
- configurable broker, port, and topic settings
- connect, publish, and disconnect lifecycle
- connection and publish error propagation
- local broker availability

## Existing configuration reviewed

`MqttPublisher` reads these environment variables:

- `MQTT_BROKER`, default `localhost`
- `MQTT_PORT`, default `1883`
- `MQTT_TOPIC`, default `cloudcrowd/telemetry`
- `MQTT_CLIENT_ID`
- `MQTT_USERNAME` and `MQTT_PASSWORD`
- `MQTT_KEEPALIVE`, default `60`
- `MQTT_QOS`, default `1`
- `MQTT_RETAIN`, default `false`
- `MQTT_TLS`, default `false`

No AWS IoT hostname, credentials, certificate, or private key was used. The test replaced the Paho client with an in-memory fake client.

## Local broker check

A TCP probe checked `localhost:1883` before the publishing test.

Result:

```text
TCP connect to (::1 : 1883) failed
TCP connect to (127.0.0.1 : 1883) failed
False
```

No local MQTT broker was available. The test therefore used the mock MQTT client described below.

## Test procedure

The test:

1. Built telemetry using the existing `build_telemetry()` function.
2. Serialized it with `json.dumps()` and parsed it again with `json.loads()`.
3. Replaced `paho.mqtt.client.Client` with a fake client that records calls.
4. Set local-only test configuration:

```text
MQTT_BROKER=127.0.0.1
MQTT_PORT=1884
MQTT_TOPIC=test/cloudcrowd/telemetry
MQTT_CLIENT_ID=local-test-client
MQTT_QOS=1
MQTT_RETAIN=true
MQTT_TLS=false
```

5. Called `publish()` and then `close()`.
6. Repeated the test with simulated connection and publish failures.

## Results

### JSON validity

Passed. The generated payload was valid JSON and round-tripped successfully:

```json
{
  "location_id": "library_01",
  "timestamp": "2026-09-17T10:30:00Z",
  "occupancy": 42,
  "capacity": 100,
  "occupancy_percentage": 42,
  "people_in": 8,
  "people_out": 5,
  "estimated_wait_minutes": 0,
  "status": "green"
}
```

### Topic and configuration

Passed. The publisher used the environment-provided values:

```text
broker: 127.0.0.1
port: 1884
topic: test/cloudcrowd/telemetry
qos: 1
retain: True
```

The publish call received the configured topic rather than the default topic.

### Lifecycle

Passed. The mock recorded the expected sequence:

```text
connect(127.0.0.1, 1884, 60)
loop_start()
publish(test/cloudcrowd/telemetry, <valid JSON>, 1, True)
disconnect()
loop_stop()
```

### Connection error handling

Passed. A simulated broker connection failure was propagated as:

```text
ConnectionError: broker unavailable
```

### Publish error handling

Passed. A simulated non-success Paho return code was converted to:

```text
RuntimeError: MQTT publish failed with code 999
```

### AWS isolation

Passed. The test used only a fake local Paho client. It did not connect to AWS IoT and did not load or use AWS credentials or certificates.

## Conclusion

The existing MQTT telemetry publisher passes the local mock-client checks for JSON validity, configurable topic selection, connect/publish/disconnect lifecycle, and error handling. Because no broker was listening on `localhost:1883`, broker-level delivery was not tested. No production code changes were required.
