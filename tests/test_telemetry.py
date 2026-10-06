from edge.mqtt.publisher import build_telemetry


def test_core_telemetry_contains_only_counts_and_state():
	payload = build_telemetry(
		"library_01",
		42,
		8,
		5,
		timestamp="2026-09-17T10:30:00Z",
	)

	assert payload == {
		"facility_id": "library_01",
		"timestamp": "2026-09-17T10:30:00Z",
		"occupancy": 42,
		"inflow": 8,
		"outflow": 5,
	}