# BusFlow smart stop gateway

The P0 server reads the camera over HTTP. It does not accept the old automatic push reporter in gateway mode. The existing YOLOX counting model stays on the Arduino.

`GET /count` returns the latest processed-frame count and device measurement timestamp. Before the first frame it returns 503. `POST /display` stores only the latest prediction and broadcasts it to the device web UI. No images leave the counting pipeline.

## Mock on the PC

From `backend/`, run `uv run python ../edge/mock_edge.py --port 8080`.

Use `POST /mock/count {"count": 15}` to change the count, `POST /mock/fail {"mode": "error"}` or `"timeout"` to test failure, and `"none"` to restore service. `GET /mock/display` shows the latest received forecast.

## Arduino UNO Q

Deploy `arduino/people-counter/` using the hardware colleague's existing workflow. Gateway mode is the default (`REPORTING_MODE=gateway`). Expose TCP port 8080 on the device/container and use the private demo LAN. Set `physical_camera_url` in `data/config/sim.yaml` to `http://<arduino-ip>:8080`, restart the backend, then select Physical / mock for Mediterraneo in the control room.

The HTTP endpoints have no authentication and are suitable only for the private demo LAN. The PC backend remains on loopback. This adds network-facing endpoints on the device, not the PC.

Real-device deployment, container port exposure, frame rate and camera accuracy remain hardware acceptance checks. Mock tests do not establish physical counter accuracy.
