"""Small local HTTP adapter for testing the telemetry API without AWS."""

import json
import os
import secrets
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from .routes import lambda_handler
from edge.input.manager import InputDeviceManager
from edge.input.factory import discover_local_cameras
from edge.pairing import PairingStore

_input_manager = None
_pairings = PairingStore()


def input_manager():
    global _input_manager
    if _input_manager is None:
        _input_manager = InputDeviceManager(input_type="webcam")
    return _input_manager


def configure_input_manager(manager):
    """Attach the HTTP control surface to the manager used by edge.main."""
    global _input_manager
    _input_manager = manager


class TelemetryRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        origin = self.headers.get("Origin")
        allowed_origin = os.getenv("EDGE_CONTROL_ORIGIN", "http://localhost:5173")
        if origin == allowed_origin:
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Vary", "Origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        origin = self.headers.get("Origin")
        allowed_origin = os.getenv("EDGE_CONTROL_ORIGIN", "http://localhost:5173")
        if origin == allowed_origin:
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Accept, Content-Type, X-Edge-Control-Token")
        self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        query = parse_qs(parsed_url.query)

        if parsed_url.path == "/health":
            self._send_json(200, {"status": "ok", "service": "cloud-crowd-analytics"})
            return

        if parsed_url.path.startswith("/pair/"):
            token = parsed_url.path.removeprefix("/pair/").strip("/")
            try:
                if _pairings.find_token(token).status != "waiting":
                    self._send_json(410, {"error": "Pairing code expired or already used"})
                    return
                self._send_pairing_page(token)
            except (KeyError, ValueError):
                self._send_json(410, {"error": "Pairing code expired or already used"})
            return

        if parsed_url.path.startswith("/pair-status/"):
            try:
                self._send_json(200, _pairings.get(parsed_url.path.removeprefix("/pair-status/")).public_status())
            except KeyError:
                self._send_json(404, {"error": "Pairing session not found"})
            return

        if parsed_url.path == "/input/status":
            self._send_json(200, input_manager().status)
            return
        if parsed_url.path == "/input/devices":
            try:
                local_cameras = discover_local_cameras()
            except Exception:
                local_cameras = []
            self._send_json(200, {"sources": [
                {"type": "webcam", "label": "Webcam / USB camera", "transports": ["opencv"]},
                {"type": "wifi", "label": "Wi-Fi / IP camera", "transports": ["rtsp", "http", "https"]},
                {"type": "rtsp", "label": "CCTV / RTSP", "transports": ["rtsp", "rtsps"]},
                {"type": "phone", "label": "Phone camera", "transports": ["webrtc", "rtsp"]},
                {"type": "bluetooth", "label": "Bluetooth device", "transports": ["metadata/control"]},
                {"type": "file", "label": "Local video file", "transports": ["filesystem"]},
            ], "local_cameras": local_cameras})
            return

        if parsed_url.path in {"/telemetry", "/telemetry/latest"}:
            facility_id = query.get("facility_id", ["library_01"])[0]
            response = lambda_handler({"pathParameters": {"facility_id": facility_id}})
            self._send_json(response["statusCode"], json.loads(response["body"]))
            return

        self._send_json(404, {"error": "Not found"})

    def _send_pairing_page(self, token):
        safe_token = escape(token, quote=True)
        body = f'''<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>CloudCrowd Phone Camera</title><style>body{{margin:0;padding:32px 22px;background:#f3efe7;color:#29322f;font:16px system-ui,sans-serif}}main{{max-width:420px;margin:auto}}h1{{font:42px Georgia,serif}}p{{color:#737b74;line-height:1.55}}button{{min-height:48px;padding:12px 20px;border:1px solid #29322f;background:#326e67;color:white;font:inherit}}.status{{margin-top:24px;padding-top:16px;border-top:1px solid #d5d1c7}}</style></head><body><main><small>CLOUDCROWD</small><h1>PHONE CAMERA</h1><p>Connect this phone as a local camera. Raw video stays on the edge network.</p><button id="start">START CAMERA</button><div class="status" id="status">Waiting for camera permission.</div><video id="preview" autoplay playsinline muted style="width:100%;margin-top:20px;display:none"></video><script>
const token="{safe_token}";let stream;const status=document.getElementById('status');document.getElementById('start').onclick=async()=>{{try{{stream=await navigator.mediaDevices.getUserMedia({{video:{{facingMode:{{ideal:'environment'}}}},audio:false}});document.getElementById('preview').srcObject=stream;document.getElementById('preview').style.display='block';const response=await fetch('/pair/'+encodeURIComponent(token)+'/connect',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{device:'Phone camera'}})}});status.textContent=response.ok?'CONNECTED — camera permission granted. WebRTC signaling is not enabled in this edge build.':'PAIRING FAILED';}}catch(error){{status.textContent=error.name==='NotAllowedError'?'CAMERA PERMISSION DENIED':'Unable to access this camera.'}}}};
</script></main></body></html>'''.encode("utf-8")
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; media-src 'self' blob:"); self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        if self.path == "/pair/session":
            session = _pairings.create()
            base = os.getenv("EDGE_PAIR_BASE_URL", f"http://{self.headers.get('Host', '127.0.0.1')}")
            self._send_json(201, {"pair_url": f"{base.rstrip('/')}/pair/{session.token}", **session.public_status()})
            return
        if self.path.startswith("/pair/") and self.path.endswith("/connect"):
            token = self.path.removeprefix("/pair/").removesuffix("/connect").strip("/")
            try:
                length = min(int(self.headers.get("Content-Length", 0)), 2048)
                payload = json.loads(self.rfile.read(length) or b"{}")
                device = payload.get("device", "Phone") if isinstance(payload, dict) else "Phone"
                if not isinstance(device, str) or len(device) > 80:
                    raise ValueError
                self._send_json(200, _pairings.consume(token, device).public_status())
            except (KeyError, ValueError, json.JSONDecodeError):
                self._send_json(410, {"error": "Pairing code expired or already used"})
            return
        if self.path.startswith("/pair-status/") and self.path.endswith("/disconnect"):
            try:
                session = _pairings.disconnect(self.path.removeprefix("/pair-status/").removesuffix("/disconnect").strip("/"))
                self._send_json(200, session.public_status())
            except (KeyError, ValueError):
                self._send_json(404, {"error": "Pairing session not found"})
            return
        expected_token = os.getenv("EDGE_CONTROL_TOKEN")
        if expected_token and self.headers.get("X-Edge-Control-Token") != expected_token:
            self._send_json(403, {"error": "Edge control authorization required"})
            return
        if self.path not in {"/input/select", "/input/connect", "/input/disconnect"}:
            self._send_json(404, {"error": "Not found"})
            return
        if self.path == "/input/connect":
            try:
                self._send_json(200, input_manager().connect())
            except RuntimeError as exc:
                self._send_json(409, {"error": str(exc), "status": input_manager().status})
            return
        if self.path == "/input/disconnect":
            self._send_json(200, input_manager().disconnect()); return
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 4096)
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict) or payload.get("input_type") not in {"webcam", "usb", "file", "rtsp", "cctv", "wifi", "phone", "bluetooth"}:
                raise ValueError("Unsupported input type")
            source = payload.get("source", payload.get("path", payload.get("url", payload.get("device_index"))))
            status = input_manager().select(source=source, input_type=payload.get("input_type"))
            self._send_json(200, status)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": str(exc) or "Invalid input selection"})
        except RuntimeError as exc:
            self._send_json(409, {"error": str(exc), "status": input_manager().status})

    def log_message(self, format_string, *args):
        print(f"[local-api] {format_string % args}")


def run_server(host="127.0.0.1", port=8000, manager=None, quiet=False):
    if manager is not None:
        configure_input_manager(manager)
    server = HTTPServer((host, port), TelemetryRequestHandler)
    if not quiet:
        print(f"[local-api] listening on http://{host}:{port}")
        print("[local-api] endpoints: /health, /telemetry, /telemetry/latest")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[local-api] shutting down")
    finally:
        server.server_close()


def start_server_in_thread(manager, host="127.0.0.1", port=8000):
    import threading
    thread = threading.Thread(target=run_server, kwargs={"host": host, "port": port, "manager": manager, "quiet": True}, daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    run_server()
