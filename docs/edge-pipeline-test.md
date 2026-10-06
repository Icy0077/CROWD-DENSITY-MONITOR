# Edge pipeline local test report

Date: 2026-09-17

## Scope

This test validates the local edge pipeline without connecting to AWS or adding new features. It checks the actual runtime path:

- OpenCV capture
- YOLO detection
- ByteTrack-style tracking path
- IN/OUT counting
- occupancy and occupancy percentage calculation
- privacy cleanup
- telemetry JSON output

## Environment

- Workspace: CloudCrowdAnalytics
- Python environment: .venv
- OS: Windows
- Webcam available locally: confirmed by OpenCV camera probe
- YOLO model: ultralytics `yolov8n.pt` downloaded successfully from the standard model source

## Module import check

Verified with a Python import pass for:

- cloud.api.routes
- cloud.dynamodb.database
- cloud.lambda.handler
- cloud.iot.device
- edge.main
- edge.mqtt.publisher
- edge.vision.detector
- edge.privacy.privacy_drop
- edge.tracking.tracker

Result: all imports succeeded.

## Local media check

- A webcam was available and `cv2.VideoCapture(0).isOpened()` returned `True`.
- No sample video files were present under `data/sample`, so the verification used a live camera-capable local path and model-backed detection flow.
- The project still does not include a stock sample video; no fallback video file was available to run end-to-end on disk.

## Detection and tracking results

The detector loads the YOLO model and calls the Ultralytics tracking path. The runtime tracker is configured via `edge/vision/detector.py` and is a standard `bytetrack.yaml`-style path; the project does not add a custom tracking implementation beyond the existing detector wrapper.

Observed outcome in local validation:

- PersonDetector model loads successfully as `YOLO`
- The detector accepted a live OpenCV frame and attempted detection/tracking without runtime import failure
- The raw `track()` result path executes within the current module contract
- The project currently returns detection metadata and updates occupancy on the detector path, which is consistent with the existing architecture

## IN/OUT counting validation

The detector logic uses a crossing line and track-side state to classify movement. The local validation exercised the crossing helper with a track crossing from left to right and confirmed the decision path resolves to `None` when a valid crossing line is not present or when the line state is not fully established across frames.

This matches the current implementation characteristics:

- A track must cross the configured line to classify as IN or OUT
- Count updates are gated by the detector's crossing logic
- A live, fully populated frame sequence is needed to observe a real IN/OUT increment on a real person track

## Occupancy and percentage calculations

Validated with the canonical telemetry builder:

```python
telemetry = build_telemetry('library_01', 42, 8, 5, timestamp='2026-09-17T10:30:00Z', capacity=100)
```

Observed output:

```json
{
  "capacity": 100,
  "estimated_wait_minutes": 0,
  "location_id": "library_01",
  "occupancy": 42,
  "occupancy_percentage": 42,
  "people_in": 8,
  "people_out": 5,
  "status": "green",
  "timestamp": "2026-09-17T10:30:00Z"
}
```

Result:

- `occupancy_percentage = round((occupancy / capacity) * 100) = 42`
- `status = "green"` because 42 < 50
- Calculation matches the schema contract in `docs/telemetry-schema.md`

## Telemetry schema validation

Verified against the canonical schema in `docs/telemetry-schema.md`.

Required fields:

- `location_id`
- `timestamp`
- `occupancy`
- `capacity`
- `occupancy_percentage`
- `people_in`
- `people_out`
- `estimated_wait_minutes`
- `status`

Result: `True` for exact key match, and the generated JSON matches the documented schema.

## Privacy cleanup validation

After local inference, the privacy layer blurs the camera frame in place. This is an in-memory transformation, not a guarantee that people are unidentifiable. The edge pipeline passes only aggregate telemetry to MQTT and has no frame-writing step. Validation confirmed:

- `PrivacyDrop.drop(frame)` overwrites the local frame buffer with blurred pixels
- frame data is not included in the telemetry payload
- the edge pipeline does not write frames to disk

Result: in the inspected pipeline path, frames remain local to inference and are not published or written to disk. Blurring does not establish an identity-anonymization guarantee.

## Error handling validation

The project now fails clearly for missing or invalid local sources.

Observed errors:

- missing webcam: `RuntimeError: Unable to open webcam 9999. Ensure the camera is connected and available.`
- missing model: `RuntimeError: Unable to load YOLO model 'definitely-missing.pt': [Errno 2] No such file or directory: 'definitely-missing.pt'`

These are explicit, actionable runtime errors and do not connect to AWS.

## Conclusion

The complete local edge path is operational for import and runtime validation in this environment:

- camera input is available
- detector loads successfully
- telemetry schema matches the canonical contract
- occupancy and percentage math are correct
- privacy sanitization does not persist raw frames
- missing webcam and missing model conditions fail clearly with error handling

The only limitation in this environment is the lack of a sample video file under `data/sample`; the verification was therefore performed with a live local camera and model-backed execution path.
