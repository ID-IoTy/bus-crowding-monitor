# BusFlow

An independent hackathon prototype for bus and stop crowding, with a passenger journey planner, an operator control room and an Arduino people-counting gateway. The integrated demo uses Turin lines **33 and 42 in both directions**. Public route geometry is a geographic reference; this project is not affiliated with the transport operator.

## Current integrated version

`test-v2` contains the integrated implementation, prepared for promotion to `main`. Previous frontend, backend, Arduino and `test` branches are preserved. See [versioning](docs/VERSIONING.md) for recovery references.

- **Passenger app:** live address/place search, automatic compatible boarding/alighting stop pairs, optional destination and date/time, up to three ordered services per line/direction, route crowding gradients and inline bus details.
- **Control room:** backend observations, vehicle locations, predictions, alerts and acknowledgement, simulation pause/speed/scenario controls and the Mediterraneo camera-mode switch.
- **One active backend:** FastAPI in `backend/`, with simulator and core connected through ingestion contracts. Separate SQLite databases hold simulated truth and processed data.
- **Camera integration:** the PC polls `GET /count` and sends `POST /display` to the Arduino or mock. The default physical-camera stop is MEDITERRANEO, GTFS ID `3380`.

The browser obtains observations and predictions from the backend. Connection failures are shown explicitly; the integrated entry point does not silently substitute the old frontend simulator. The colleague's original `server/` is retained as a reference, not a second server to start.

## Assumptions and limitations

All service movements, timetables and historical training observations are synthetic. Route geometry and reference travel offsets come from the existing public GTFS fixture. The three passenger options are three services, not the whole simulated fleet. Service is scheduled between 06:00 and 23:00.

The demo assumes **70 total places per bus**. Actual capacity is not verified and seated capacity is unknown. No seat availability is promised. Bus levels use green <=60%, yellow >60–75%, orange >75–90%, red >90%; boarding risk is a separate warning.

P0 forecasts combine synthetic historical averages with recent counts and Monte Carlo propagation through estimated alighting and capacity-limited boarding. Line allocation and passer-by behaviour remain model assumptions. Validated reliability/accuracy is unavailable; Monte Carlo probabilities are not calibrated accuracy. Missing or stale readings older than 180 simulated seconds are unavailable, never zero. Advanced historical insights and calibration remain P1.

## Start locally on Windows

Requirements: Python 3.12 through `uv`, Node.js with npm, and Internet access for map tiles and online place search. Run the following manually in PowerShell from the repository directory.

Prepare the backend and generate one synthetic historical week (bootstrap may take several minutes; run it before starting the server):

```powershell
cd backend
uv sync --extra dev
uv run python -m app.cli bootstrap --weeks 1
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Keep that terminal open. In another terminal:

```powershell
cd frontend
npm ci
npm run dev -- --port 5174
```

Open the passenger app at `http://127.0.0.1:5174/#citizens` and the control room at `http://127.0.0.1:5174/#operators`. API documentation: `http://127.0.0.1:8000/docs`. The default simulated start is **12 October 2026, 07:00 Europe/Rome**, after a warm-up from 06:00. Pause and x1–x60 speed are available in the control room.

The PC backend has no authentication and binds only to `127.0.0.1`. CORS permits configured localhost/127.0.0.1 frontend ports 5173 and 5174. Do not expose the backend publicly. `VITE_API_URL` can override the frontend API URL; custom origins require a matching backend CORS configuration.

## Demonstrate the camera without hardware

In a third terminal, from `backend/`:

```powershell
uv run python ../edge/mock_edge.py --port 8080
```

Select Physical / mock for Mediterraneo in the control room. In a separate terminal, change the mock count:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/mock/count -ContentType application/json -Body '{"count":15}'
Invoke-RestMethod -Uri http://127.0.0.1:8080/mock/display
```

The gateway polls periodically and around bus visits. New counts influence the forecast; the mock receives the stop-display payload. `/mock/fail` accepts `{"mode":"error"}`, `{"mode":"timeout"}` and `{"mode":"none"}`. Details and real-device configuration: [edge guide](edge/README.md).

The Arduino keeps the existing on-device detection model. Gateway mode is the default and disables the legacy periodic push reporter. Its HTTP service is network-facing on the private LAN, without authentication; port/container exposure and real camera behaviour require hardware acceptance. No images are sent to the central backend.

## Verification

```powershell
cd backend
uv run pytest -q
uv run ruff check .
```

```powershell
cd frontend
npm test
npm run build
```

Regenerate OpenAPI and TypeScript contracts with `./scripts/gen-types.ps1` from the repository root. [API contract](docs/API_CONTRACT.md) documents the integrated interface.

The merge checks include 10 backend tests (including mock count → observation → changed prediction → display), 19 frontend/domain tests and the production build. Frontend tests include preserved standalone-model tests; they do not establish full live-browser end-to-end coverage. Backend/frontend HTTP responses and the corrected passenger map were checked locally. Full desktop/mobile integrated interaction acceptance and real Arduino verification remain separate checks; mock tests do not validate the physical counting model.
