# People Counter – Arduino UNO Q edge device

Arduino App Lab app that counts the people currently visible to the camera
(not a cumulative total) and sends the count to the central backend
(`backend` branch, `server/`).

- Hardware: Arduino UNO Q + Media Carrier + Sony IMX219 (CSI, `CAMERA0`)
- Model: `yolox-object-detection` (App Lab built-in), filtered to the `person` label
- Bricks: `arduino:video_object_detection`, `arduino:web_ui`

## How it talks to the server

`python/server_client.py` posts JSON over HTTP with the `X-API-Key` header,
using the contract in `server/app/schemas/ingest.py`:

| `DEVICE_MODE` | Endpoint | Count field |
|---|---|---|
| `stop` (default, camera at a bus stop) | `POST /ingest/stop-event` | `people_waiting`, `event_type: "periodic"` |
| `bus` (camera on board) | `POST /ingest/bus-event` | `passengers_onboard`, `door_status: "closed"` |

When it sends:
- When the count changes. The new value must hold for 2 s, so frame-to-frame
  flicker (0/1/0) is not sent, and sends are at least 5 s apart.
- Every 60 s with the current value, per the stop cadence in the main README.

Sending runs in its own thread, so a slow or offline server never blocks
detection. Failed sends are retried after 5 s. The result of each send
appears in the local Web UI ("Server centrale" card).

## Configuration

Edit the block at the top of `python/main.py`. You can also override each
value with an environment variable of the same name.

| Name | Default | Notes |
|---|---|---|
| `SERVER_URL` | `http://192.168.22.188:8000` | IP of the PC running the backend |
| `API_KEY` | `dev-key` | Must match `SMARTBUS_API_KEY` on the server |
| `DEVICE_MODE` | `stop` | `stop` or `bus` |
| `STOP_ID` | `R1-S05` | Seeded IDs: `R1-S00`…`R1-S39`, `R2-S00`…`R2-S39` |
| `BUS_ID` / `ROUTE_ID` | `BUS-01` / `R1` | Only used in `bus` mode |
| `PERIODIC_INTERVAL` | `60` | Seconds |

The backend must listen on the network, not only on localhost:

```bash
cd server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`demo.ps1` binds to `127.0.0.1`, which the board cannot reach. On Windows, also
allow inbound TCP 8000 in the firewall.

## Deploy

Run `redeploy.bat` from this folder. It copies `app.yaml`, `python/` and
`assets/` to `/home/arduino/ArduinoApps/people-counter` over SSH and then runs
`arduino-app-cli app restart .`.

Pages served by the board:
- Local UI: `http://<board-ip>:7000`. The WebUI Brick serves `assets/`.
- Annotated video stream: `http://<board-ip>:4912/embed`. The video object
  detection brick serves this.

## Layout

```
app.yaml                  App Lab bricks + model
python/main.py            detection callback, local UI messages, config
python/server_client.py   backend client (stdlib only, no extra deps)
assets/                   local Web UI (index.html, app.js, style.css)
assets/libs/              official WebUI Brick JS (socket.io + arduino.js)
```

## Known limitations

- The local UI on ports 7000 and 4912 has no authentication. Use it only on a
  trusted network.
- `bus` mode sends on count changes, not on actual door-close events. The
  board has no door signal.
- The device does not send `pre_arrival` or `post_departure` stop events
  because it has no bus-arrival trigger. As a result, backend correlation for
  this stop only happens through bus events.
