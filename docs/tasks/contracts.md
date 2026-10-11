# Contracts and repository skeleton

Everything else depends on this file. It produces the typed contracts that the simulator, the core and the frontend share, and the empty repository structure.

- **May edit:** `backend/` (project files, `app/contracts`, `app/main.py`, `app/cli.py`, `tests/contracts`, `tests/test_isolation.py`), `scripts/`, `data/config/`, `.gitignore`.
- **SPEC:** [section 2](../SPEC.md#2-system-architecture) (layout, isolation), [section 6](../SPEC.md#6-message-contracts-who-sends-what-to-whom) (contracts, ID formats, common rules), [section 9 constants](../SPEC.md#constants-dataconfigmodelyaml), [section 13](../SPEC.md#13-dev-environment).

---

## C1 - Contracts, skeleton and type generation

- **Priority:** P0
- **Status:** todo
- **Depends on:** none

### Objective

Create the backend project and the Pydantic v2 models for every message and view in SPEC section 6, the two ports, and the tooling that turns them into TypeScript types.

### Instructions

1. **Backend project:**
   - `backend/pyproject.toml` for Python 3.12, managed with uv, with the backend stack of AGENTS.md pinned to exact versions;
   - ruff configured in `pyproject.toml`;
   - commit `uv.lock`.
2. **`.gitignore`:** `*.sqlite`, `data/history/`, `backend/artifacts/`, `node_modules/`, `.venv/`.
3. **`backend/app/contracts/`:**
   - `ids.py`: regex patterns and helper constructors for every ID format in SPEC section 6 (`make_trip_id(line, direction, start)` and so on).
   - `common.py`:
     - `Kind = Literal["observed", "predicted", "simulated"]`, `Source = Literal["simulated", "physical"]`, `Level = Literal["green", "yellow", "orange", "red"]`, `Trigger`, `CameraMode`;
     - a timezone-aware datetime type that rejects naive datetimes.
   - `events.py`: `VehicleApproach`, `VehicleDeparture`.
   - `observations.py`: `CameraObservation`, `CountRequest`, `DisplayBus`, `DisplayPayload`, `EdgeCount` (the Arduino `GET /count` response).
   - `views.py`:
     - `ObservedValue`, `PredictedValue`, `UnavailableValue` (`value: null`, `status: "stale" | "missing"`);
     - `LineView`, `StopView`, `NextBusView`, `VehicleView`, `JourneyView`, `AlertView`, `CalibrationView`, `HealthView`.
     All fields follow the example payloads in SPEC section 6.
   - `sim.py`: `ClockCommand` (speed in [1, 60], paused), `SimState`, `ScenarioCommand`, `CameraModeCommand`, `TruthView`.
   - `ws.py`: `WsEnvelope` with `type` in `clock`, `vehicles`, `stops`, `predictions`, `alerts`, and a discriminated `data` per type.
   - `ports.py`:
     - `IngestPort` Protocol: `approach`, `departure`, `observation`, each returning `IngestResult = Literal["accepted", "duplicate"]` and raising `pydantic.ValidationError` on invalid input;
     - `CameraPort` Protocol: `count_request(camera_id, CountRequest) -> None`, `display(camera_id, DisplayPayload) -> None`.
4. **Config:**
   - `data/config/model.yaml` with every constant of SPEC section 9;
   - `data/config/sim.yaml` with every parameter of SPEC section 4, plus `seed`, `start_time`, `hubs: []` and `physical_camera: {camera_id: null, base_url: null}`;
   - `app/config.py` loads both into Pydantic models.
5. **`app/main.py`:**
   - a FastAPI app with CORS for `http://localhost:5173` only, `GET /api/health` (sim_time and model_version may be null until wired), and `GET /api/ws-schema` returning an example `WsEnvelope`;
   - a comment block marking the wiring section that K1 fills in.
6. **`app/cli.py`:**
   - an argparse CLI with an `export-openapi <path>` subcommand that writes `app.openapi()` to a file without starting a server;
   - placeholders for the other subcommands (`import-gtfs`, `generate-history`, `replay`, `train`, `bootstrap`) that exit with "not implemented yet (task Sx/Kx)".
7. **`scripts/gen-types.ps1`:**
   - runs `uv run python -m app.cli export-openapi ../frontend/openapi.json` from `backend/`;
   - then `npx openapi-typescript openapi.json -o src/api/generated.ts` from `frontend/`, using the `openapi-typescript` dev dependency pinned in `frontend/package.json` (added by O1);
   - fails with a clear message if `frontend/node_modules` does not exist yet.
8. **`backend/tests/test_isolation.py`:** walks every `.py` file under `app/core` and fails if any `import app.sim` or `from app.sim` appears. Passes trivially while `app/core` is empty.

### Tests (`backend/tests/contracts/`)

- Every example JSON in SPEC section 6 parses into its model (copy them into `tests/contracts/examples/`).
- Invalid payloads are rejected:
  - missing required field;
  - negative `boarded`;
  - naive datetime;
  - unknown `trigger`;
  - malformed `trip_id`;
  - `ClockCommand(speed=0)` and `ClockCommand(speed=61)`.
- ID helpers round-trip: `make_visit_id(make_trip_id("42", 0, t), 12) == "visit-42-0-20261012-0730-s12"`.
- `UnavailableValue` serialises `value` as `null`, never `0`.
- `export-openapi` writes a JSON file that contains the `VehicleDeparture` and `WsEnvelope` schemas.

### Acceptance

```powershell
cd backend
uv sync
uv run pytest tests/contracts tests/test_isolation.py   # all green
uv run ruff check .                                       # "All checks passed!"
uv run python -m app.cli export-openapi openapi.json      # file created, contains "VehicleDeparture"
```

### Demo

`uv run pytest tests/contracts -v` shows every SPEC example accepted and every invalid case rejected.
