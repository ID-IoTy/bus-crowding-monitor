"""Small HTTP gateway on the device: snapshots and latest display, never frames."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def start_gateway(reading, on_display, port=8080):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/count":
                self.send_error(404)
                return
            payload = reading()
            if payload is None:
                self.send_error(503, "No processed frame yet")
                return
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != "/display":
                self.send_error(404)
                return
            try:
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= 65536:
                    raise ValueError("Invalid payload size")
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload.get("stop_id"), str) or not isinstance(payload.get("generated_at"), str) or not isinstance(payload.get("buses"), list):
                    raise ValueError("Invalid display payload")
                for bus in payload["buses"]:
                    if not all(k in bus for k in ("line_id", "eta_s", "predicted_onboard", "interval_80", "level", "may_not_fit")):
                        raise ValueError("Invalid bus display")
                on_display(payload)
            except (ValueError, TypeError, KeyError):
                self.send_error(422, "Invalid display payload")
                return
            self.send_response(204)
            self.end_headers()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, name="camera-gateway", daemon=True).start()
    return server
