# Edge: Arduino UNO Q smart stop and its mock

The physical smart stop counts people on the device and shows the predictions for the next buses. It is a separate hardware workstream. The backend only depends on the HTTP contract below.

- **May edit:** `edge/` only.
- **SPEC:**
  - [section 6](../SPEC.md#6-message-contracts-who-sends-what-to-whom) (display payload, Arduino `GET /count` response);
  - [section 11](../SPEC.md#11-physical-camera-switch) physical camera switch.
- **Hardware:**
  - the Arduino UNO Q: its Linux MPU runs the HTTP server and the counting model, and its MCU drives peripherals;
  - the production kit in the business infographic (ESP32-S3 + LoRa) is out of scope.

## Contract (fixed)

| Endpoint | Request | Response | Rules |
| --- | --- | --- | --- |
| `GET /count` | none | `200 {"count": int ≥ 0, "measured_at": ISO 8601 with offset}` | Answer in under 2 s (the gateway timeout). `count` is the number of people in frame **now**. `measured_at` is device wall-clock time |
| `POST /display` | display payload of SPEC section 6 (`stop_id`, `generated_at`, `buses[]`) | `204` | Keep only the last payload, in memory. Invalid payload → `422` |

- Port 8080. The base URL is set in `data/config/sim.yaml` (`physical_camera.base_url`).
- **Privacy:** no frame or image is written to disk or sent over the network. Only the number leaves the counting code.
- **Security:** no authentication in the demo. Use a private network. `X-Api-Key` is future work (SPEC section 6).

---

## E1 - Python mock of the Arduino

- **Priority:** P0
- **Status:** todo
- **Depends on:** C1

### Objective

A drop-in mock of the Arduino, so the backend and the frontend can be built and demoed without the device.

### Instructions

1. Write `edge/mock_edge.py`, a small FastAPI app implementing the contract on `--port 8080`. It runs with the backend environment: `cd backend; uv run python ../edge/mock_edge.py --port 8080`.
2. Control endpoints, mock only:
   - `POST /mock/count {"count": n}` sets the count;
   - `POST /mock/fail {"mode": "none" | "timeout" | "error"}` simulates a slow device (sleeps 3 s) or a `500`.
3. `GET /mock/display` returns the last display payload.
4. It logs every request on one line.

### Tests

Tests live in `edge/tests/` and run with `cd backend; uv run pytest ../edge/tests`:

- the contract responses;
- the `422` on an invalid display payload;
- the fail modes.

### Acceptance

```powershell
cd backend
uv run pytest ../edge/tests   # green
```

### Demo

The presenter changes the count with `POST /mock/count` and the dashboard follows (with S5).

---

## E2 - HTTP server on the Arduino UNO Q

- **Priority:** P0
- **Status:** todo
- **Depends on:** E1

### Objective

The same contract as the mock, served by the real device on the demo LAN.

### Instructions

- Implement the same contract on the Linux side of the UNO Q, port 8080. Framework of the hardware colleague's choice.
- **The mock is the reference:** the same requests must give the same response shapes.
- `GET /count` returns the latest count from E3. Before E3 is ready, return a value set by a button or a constant.
- `POST /display` hands the payload to E4.
- Write `edge/README.md`:
  - setup on the device;
  - how to start the server;
  - how to find the device IP;
  - how to point `sim.yaml` at it.

### Tests

The contract checks from E1 run against the device, using a `--base-url` option on the E1 tests.

### Acceptance

```powershell
cd backend
uv run pytest ../edge/tests --base-url http://<arduino-ip>:8080   # contract tests green against the device
```

### Demo

The backend reads counts from the real device.

---

## E3 - On-device people counting

- **Priority:** P0
- **Status:** todo
- **Depends on:** E2

### Objective

Count the people in the camera frame on the device, within the contract.

### Instructions

The counting model, camera and pipeline are **chosen by the hardware colleague**. This task fixes only the contract:

- `count` = people currently in frame, refreshed at least every 2 s, served by `GET /count` in under 2 s;
- no frames stored or transmitted;
- if the model is not ready, `GET /count` still answers with the last known count, or `503` if there has never been one. The gateway treats a `503` as no observation.

Document the chosen model, its frame rate and a rough accuracy check (for example 10 manual counts against the device) in `edge/README.md`.

### Tests

A manual check with 0, 1, 3 and 5 people in frame, recorded in `edge/README.md`.

### Acceptance

The manual check is recorded, and E2's contract tests are still green.

### Demo

Step 5 of the demo script: people step in front of the camera and the predictions move.

---

## E4 - Basic stop display

- **Priority:** P0
- **Status:** todo
- **Depends on:** E2, K3

### Objective

Show the predictions for the next buses on the physical stop.

### Instructions

- Render the last `POST /display` payload. For each bus:
  - line;
  - ETA in minutes;
  - level as text (and colour if the hardware allows);
  - confidence in %;
  - a "may not fit" warning when `may_not_fit` is true.
- Display hardware is the colleague's choice (screen, LED matrix, or a local web page served by the device).
- With no payload yet, show "No prediction available", never zeros.

### Tests

Manual: post the SPEC display example with `Invoke-RestMethod` and check both buses are shown.

### Acceptance

The SPEC display example renders correctly, and a photo is added to `edge/README.md`.

### Demo

The stop shows the same prediction as the dashboard.

---

## E5 - Advanced display

- **Priority:** P2
- **Status:** todo
- **Depends on:** E4

### Objective

Richer graphics on the stop display.

### Instructions

- Richer graphics: crowding icons, interval_80, and scrolling for more than two buses.
- Optional voice announcements are future work (SPEC section 1) and are not part of this task.

### Acceptance

Agreed with the team when started.
