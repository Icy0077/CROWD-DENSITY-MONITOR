"""Small local HTTP adapter for testing the telemetry API without AWS."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from .routes import lambda_handler


class TelemetryRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Accept, Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        query = parse_qs(parsed_url.query)

        if parsed_url.path == "/health":
            self._send_json(200, {"status": "ok", "service": "cloud-crowd-analytics"})
            return

        if parsed_url.path in {"/telemetry", "/telemetry/latest"}:
            facility_id = query.get("facility_id", ["library_01"])[0]
            response = lambda_handler({"pathParameters": {"facility_id": facility_id}})
            self._send_json(response["statusCode"], json.loads(response["body"]))
            return

        self._send_json(404, {"error": "Not found"})

    def log_message(self, format_string, *args):
        print(f"[local-api] {format_string % args}")


def run_server(host="127.0.0.1", port=8000):
    server = HTTPServer((host, port), TelemetryRequestHandler)
    print(f"[local-api] listening on http://{host}:{port}")
    print("[local-api] endpoints: /health, /telemetry, /telemetry/latest")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[local-api] shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
