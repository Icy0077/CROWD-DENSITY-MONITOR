# System architecture

## Data path

1. OpenCV reads a webcam, local video, or RTSP-compatible source.
2. YOLO detects person class only; ByteTrack provides persistent track IDs.
3. The configured virtual line emits at most one crossing event per track per frame.
4. The edge process maintains `occupancy = previous occupancy + IN - OUT`, never below zero.
5. Privacy processing creates a local display copy. Raw frames are not sent to MQTT or AWS.
6. The MQTT publisher sends the small edge telemetry payload over TLS when AWS variables are configured.
7. AWS IoT Core routes the topic to the telemetry Lambda.
8. Lambda validates and normalizes the message, calculates wait time, and writes one latest-state DynamoDB item keyed by `location_id`.
9. API Gateway invokes the read Lambda for `GET /telemetry/latest`.
10. React polls the API and displays only returned backend values.

## State and contracts

DynamoDB contains one latest validated state per facility. Conditional writes reject older timestamps so delayed messages cannot roll state backwards. The canonical API response is defined in [telemetry-schema.md](telemetry-schema.md). The frontend consumes the canonical names and does not use a production mock fallback.

## Privacy boundary

Detection and tracking happen locally. The cloud boundary begins at aggregate counts and occupancy. No image, face, identity, or raw video field is part of the telemetry contract.
