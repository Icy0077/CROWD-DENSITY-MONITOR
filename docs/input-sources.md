# CloudCrowd input sources

All sources implement the same `InputSource` contract. The edge pipeline receives frames, then applies YOLO/ByteTrack, local privacy processing, line crossing, and five-second aggregate MQTT telemetry. Raw frames remain on the edge device.

## Supported now

- **Webcam**: the default OpenCV device (`0`).
- **USB camera**: an OpenCV device index, using the same adapter as a webcam.
- **Local video file**: useful for offline validation.
- **RTSP/CCTV**: IP cameras, DVRs, and NVRs that expose RTSP.
- **Wi-Fi/IP camera**: RTSP or compatible HTTP/MJPEG URL through the network adapter.
- **Phone RTSP**: supported when a phone app/service exposes an RTSP-compatible stream.

Examples:

```powershell
# Default webcam
.\.venv\Scripts\python.exe -m edge.main --input-type webcam --source 0

# USB camera
.\.venv\Scripts\python.exe -m edge.main --input-type usb --source 1

# CCTV or RTSP camera (keep credentials in environment variables, never in source)
.\.venv\Scripts\python.exe -m edge.main --input-type rtsp --source "rtsp://camera-host:554/stream"

# Phone source with an RTSP transport
.\.venv\Scripts\python.exe -m edge.main --input-type phone --source "rtsp://phone-host/stream"
```

Equivalent configuration uses `INPUT_TYPE`, `INPUT_SOURCE`, `CAMERA_USERNAME`, and `CAMERA_PASSWORD`. Credential-bearing URLs are redacted in source descriptions and errors. The default remains `FACILITY_ID=facility-1` and `REPORTING_INTERVAL_SECONDS=5`.

## Phone browser mode

The phone adapter includes a signaling boundary for a future local WebRTC server. A complete WebRTC signaling/media server is **not implemented in this repository**, so the browser pairing page must not be presented as operational yet. The intended local URL is `http://<edge-device>:<port>/camera`; any implementation must request browser camera permission, keep media local, and deliver frames to the phone adapter rather than AWS.

The local control server now provides a short-lived QR pairing flow. Start it on the edge PC:

```powershell
$env:EDGE_PAIR_BASE_URL = "http://192.168.1.20:8000"
.\.venv\Scripts\python.exe -m cloud.api.local_server
```

In the dashboard select **Phone**, choose **Generate QR**, and scan it from a phone on the same Wi-Fi network. The QR contains only a random two-minute one-use pairing URL. The phone page requests camera permission and shows the local preview; actual WebRTC frame delivery still requires a configured signaling/media adapter, and the UI states that limitation explicitly.

For browser camera permission and production WebRTC, use HTTPS where required by the browser. Do not disable the Windows firewall broadly; allow only the local control port (8000) on the private network profile if Windows prompts for it.

## Bluetooth

Bluetooth is intentionally isolated from video processing. `BluetoothDeviceAdapter` supports discovery, pairing/selection, connection status, and metadata/control mocks. Bluetooth connected — no compatible video stream exposed is the expected state unless hardware provides a supported video transport. It does not fake frames and does not require physical hardware in tests.

## Privacy and aspect ratio

Privacy is on by default and is independent of source type. Press `1` to enable local privacy processing or `2` to disable the local display blur. AWS receives telemetry only. Display transforms should use the aspect-ratio-safe helpers in `edge.input.geometry`; never stretch phone, webcam, CCTV, or RTSP frames.

## Local control API

The optional local edge control surface is intended for a local-only bind and provides:

`GET /input/status`, `GET /input/devices`, `POST /input/select`, `POST /input/connect`, and `POST /input/disconnect`.

It controls the edge connection; it is not part of the public AWS API and must not expose credentials or raw camera streams. The React Settings panel uses `VITE_EDGE_CONTROL_URL` and reports the edge as unavailable when it cannot connect.

## Troubleshooting and limitations

- A dropped live frame is retried by the RTSP adapter; repeated failures end the source cleanly.
- Requested resolution/FPS values are hints; actual camera capabilities win, and measured processing FPS is displayed.
- RTSP support depends on the OpenCV/FFmpeg build and camera transport.
- Phone WebRTC and Bluetooth video require real device/server integration and hardware testing.
- MQTT/AWS configuration is unchanged; telemetry is aggregated at the reporting interval and is never published per frame.
