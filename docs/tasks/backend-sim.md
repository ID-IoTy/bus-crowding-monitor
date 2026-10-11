# Backend simulator (`app/sim`)

The simulator owns the simulated world and the clock. It produces sensor data (APC events, camera observations) and sends it to the core only through `IngestPort`. It receives count-requests and display updates only through `CameraPort`.

- **May edit:** `backend/app/sim/`, `backend/app/api/sim_routes.py`, the sim subcommands in `backend/app/cli.py`, `backend/tests/sim/`, `data/gtfs/`, `data/scenarios/`, `data/config/sim.yaml`.
- **Must not:** import anything from `app/core`, or touch `server.sqlite`.
- **SPEC:**
  - [section 2](../SPEC.md#2-system-architecture) architecture and isolation;
  - [section 3](../SPEC.md#3-clock-and-scheduler) clock and scheduler;
  - [section 4](../SPEC.md#4-world-simulator) world simulator;
  - [section 5](../SPEC.md#5-stop-visit-sequence) stop visit sequence;
  - [section 6](../SPEC.md#6-message-contracts-who-sends-what-to-whom) contracts;
  - [section 11](../SPEC.md#11-physical-camera-switch) physical camera.

Tests use a recording fake `IngestPort` (`tests/sim/fakes.py`) that stores every message, so this system can be built before the core.

---

## S1 - GTFS import of lines 33 and 42

- **Priority:** P0
- **Status:** todo
- **Depends on:** C1

### Objective

A labelled static fixture with the real geography of lines 33 and 42, used by the simulator and loaded by the core.

### Instructions

1. Write `app/sim/gtfs_import.py` and the CLI subcommand `import-gtfs --zip <path-or-url> --lines 33 42 --out ../data/gtfs/fixture_33_42.json`. The default source is the GTT archive URL in SPEC section 14.
2. For each line (`route_short_name`) and `direction_id`:
   - the representative pattern is the most frequent ordered stop sequence among weekday trips;
   - take the shape of that pattern;
   - take `planned_offset_s` from the median trip of the pattern (arrival at the stop minus departure from the first stop).
3. Output:
   - lines (id, name, colour from GTFS or a default);
   - stops (`gtt-{stop_id}`, name, lat, lon);
   - route stops (line, direction, sequence, stop_id, planned_offset_s);
   - shapes (list of [lat, lon]);
   - computed `shared` flag per stop;
   - metadata `{source_url, downloaded_at, note: "GTT GTFS extract, static geography only. Reuse terms to be checked before redistribution."}`.
4. Commit the fixture so nobody else needs the network.
5. If `hubs` in `sim.yaml` is empty, the loader returns shared stops + termini as hubs.

### Tests

- A unit test on a tiny synthetic GTFS zip built in `tests/sim/fixtures/`.
- Tests on the committed fixture:
  - both lines and both directions present;
  - at least 10 stops per direction;
  - sequences contiguous from 1;
  - `planned_offset_s` strictly increasing;
  - every coordinate inside Turin (lat 44.95-45.15, lon 7.55-7.80);
  - at least one stop shared by 33 and 42.

**If no shared stop exists, stop and report to the team**: the choice of lines must be revisited (SPEC section 17).

### Acceptance

```powershell
cd backend
uv run python -m app.cli import-gtfs --lines 33 42 --out ../data/gtfs/fixture_33_42.json
uv run pytest tests/sim -k gtfs        # green; the test output lists the shared stop names
```

### Demo

The fixture lists the stops of 33 and 42 in order, with the shared section highlighted in the test output.

---

## S2 - Clock, scheduler and bus movement

- **Priority:** P0
- **Status:** todo
- **Depends on:** C1, S1

### Objective

The simulated clock (x1 to x60, pause) and the discrete-event scheduler, with buses running the timetable along the real shapes and emitting `approach` and `departure` events. No passengers yet: boarded and alighted are 0.

### Instructions

1. `app/sim/clock.py` (`SimClock`) and `app/sim/scheduler.py` (heap, tie-break counter, `schedule(at, fn)`, `run_until(t)`, async real-time loop of SPEC section 3).
   - The monotonic time source is injectable so tests can fake real time.
   - Hooks: `on_tick` for the core's dirty-trip recompute and `every(period_s, fn)` for the 15 s recompute and the WS push.
2. `app/sim/vehicles.py`:
   - trip schedule per line and direction (headway, service hours);
   - greedy vehicle assignment with layover;
   - fleet size;
   - travel time = planned difference × lognormal noise;
   - dwell time formula;
   - `approach` event 60 s before arrival (rules in the SPEC parameters table);
   - `departure` event with `is_terminus` at the last stop;
   - position interpolated along the shape.
3. `app/sim/factory.py`: `build_sim(config, clock: SimClock, ingest: IngestPort) -> Simulation` (the clock is created first, so the core can receive `clock.now` before the simulator exists) with `.clock`, `.scheduler`, `.camera_port` (added in S3), `.start()` (warm-up from 06:00, then real-time loop), `.stop()`, `.state()`.
4. Routes in `app/api/sim_routes.py`: `GET /sim/state`, `POST /sim/clock` (`ClockCommand`, `422` outside [1, 60]). The router gets the `Simulation` from `app.state`.
5. CLI subcommand `dry-run --hours 1`: runs batch mode from the start time and prints trips, vehicles and events per type.

### Tests

- Same seed gives the identical event list; a different seed gives a different one.
- Fake time:
  - at x10, 1 s of real time advances the sim by 10 s ± 0.1 s;
  - paused, sim time does not move;
  - a speed change applies on the next tick.
- Events with equal time run in insertion order.
- Fleet per line = `ceil(round_trip_time / headway)`.
- Every trip:
  - emits approach then departure for each stop, in sequence order;
  - `trip_id`, `event_id` and `visit_id` match the SPEC formats;
  - has `is_terminus = true` only at the last stop.
- No trip starts outside service hours.
- `approach.eta_s` is 60, or the leg duration when the leg is shorter than 60 s.

### Acceptance

```powershell
cd backend
uv run pytest tests/sim -k "clock or scheduler or vehicles"   # green
uv run python -m app.cli dry-run --hours 1                    # prints trips > 0 for 33 and 42, both directions
```

### Demo

`dry-run` prints the buses of the first simulated hour. Once K1 wires the simulator, the buses move on the map (O2).

---

## S3 - Passengers, APC, simulated cameras, scenarios and ground truth

- **Priority:** P0
- **Status:** todo
- **Depends on:** S2

### Objective

The agent-based world of SPEC section 4: passengers, passers-by, boarding, alighting and abandonment, with APC and camera sensor models, YAML scenarios, ground truth in `sim.sqlite` and the simulated side of `CameraPort`.

### Instructions

1. `app/sim/world.py`:
   - Poisson arrivals per (stop, line, direction) with the multipliers of SPEC section 4 (peaks, hubs, shared section, weekend, daily noise);
   - destinations weighted by attraction;
   - lognormal patience and abandonment events;
   - FIFO boarding capped at total capacity;
   - alighting at destination;
   - passers-by with time in frame.
2. `app/sim/sensors.py`: the APC model (2% error, drift +1 with probability 0.3 per stop) and the camera model (8% gaussian, occlusion above 20), exactly as in the SPEC.
3. `app/sim/gateway.py` (simulated mode):
   - periodic readings every 60 s with a random per-camera offset;
   - `CameraPort.count_request` schedules a reading at `sim_now + delay_s` and emits the observation with the same `request_id` and `visit_id`;
   - `CameraPort.display` stores the last payload per stop, in memory.
4. `app/sim/scenarios.py`: load `data/scenarios/{normal,rush_hour,overcrowding}.yaml`. Add routes `GET /sim/scenarios` and `POST /sim/scenario` (`404` for an unknown name).
5. `app/sim/truth.py`:
   - `sim.sqlite` through its own SQLAlchemy engine;
   - passengers with outcome, and true counts per stop and per bus sampled every 60 s;
   - rows have `dataset`, and `live` rows are deleted at startup;
   - `GET /sim/truth` returns `TruthView` with `kind = "simulated"`.

### Tests

- **Conservation:** at any time, arrived = waiting + onboard + alighted + abandoned.
- True onboard ≤ 95 at all times, and 0 at the end of every trip.
- With the same seed and hour, mean waiting under `rush_hour` > under `normal`.
- `overcrowding`: arrivals at `target_stop_id` are about 10 times normal for 20 min, then back.
- Abandonment happens when buses are removed (test scenario with no buses).
- APC: some trips end with declared onboard ≠ 0; the mean error of boarded is within 2 percentage points of 0.
- Camera: on average it undercounts when true in-frame > 20.
- A `count_request` with `delay_s = 10` gives exactly one observation 10 s later, with matching `request_id`, `visit_id` and `trigger`.
- Periodic observations are 60 s apart per camera.
- **Tuning check:** with `rush_hour`, at least one bus on the shared section reaches a true onboard ≥ 90 within 30 simulated minutes. If not, tune the multipliers and write the new values in the SPEC parameters table.

### Acceptance

```powershell
cd backend
uv run pytest tests/sim -k "world or sensors or gateway or scenario or truth"   # green
```

### Demo

At x10, `GET /sim/truth` shows waiting passengers growing at hubs. `POST /sim/scenario {"name": "rush_hour"}` makes them grow faster.

---

## S4 - Synthetic history, 1 week

- **Priority:** P0
- **Status:** todo
- **Depends on:** S3

### Objective

One week of synthetic history (2026-10-05 to 2026-10-11) as JSONL, which looks exactly like live data, for the core to replay and train on.

### Instructions

1. `app/sim/history.py` runs the simulator in batch mode (no pacing, physical mode forbidden) over the history window, with the `normal` scenario and its time-of-day peaks.
2. It uses a `HistoryRecorder` that implements `IngestPort` and appends each message to `data/history/{approach,departure,observation}.jsonl`.
   - Because no core runs during generation, the recorder also issues the count-requests the core would issue: pre-arrival at each approach, post-departure 10 s after each departure (SPEC section 5), with valid `request_id`.
   - This mirrors the core's policy and stays inside `app/sim`.
3. Ground truth goes to `sim.sqlite` with `dataset = history`.
4. CLI: `generate-history --weeks 1 --seed 42` (prints message counts and duration). The replay into the core is task K2.

### Tests (on 1 simulated day for speed)

- Two runs with the same seed give byte-identical files.
- Every line validates against its contract model.
- Every departure has a matching approach.
- At least 95% of departures have a post-departure observation.
- All timestamps are inside the window.

### Acceptance

```powershell
cd backend
uv run pytest tests/sim -k history                               # green
uv run python -m app.cli generate-history --weeks 1 --seed 42    # finishes in under 3 minutes, prints counts per file
```

### Demo

`data/history/` contains a week of APC events and camera counts for lines 33 and 42.

---

## S5 - Physical camera mode and world sync

- **Priority:** P0
- **Status:** todo
- **Depends on:** S3, E1

### Objective

Switch the configured camera between simulated and the Arduino at runtime, as in SPEC section 11.

### Instructions

1. Physical mode in `app/sim/gateway.py`:
   - every scheduled reading calls `GET {base_url}/count` with `httpx.AsyncClient`, 2 s timeout, at most one request in flight per camera (skip if busy);
   - on response: world sync (disable passers-by at that stop, add or remove waiting agents to match `count`, record `added_by_sync` / `removed_by_sync` in truth);
   - then emit the observation with `source = "physical"`, `measured_at = sim_now` and `device_measured_at` from the device;
   - on timeout or error: no observation, one warning log line.
2. `CameraPort.display` for a physical camera also sends `POST {base_url}/display`. Failures are logged and ignored.
3. Routes:
   - `GET /sim/cameras` → `[{camera_id, stop_id, mode, last_display}]`;
   - `POST /sim/cameras/{camera_id}/mode` → `404` unknown camera, `409` if it is not the configured physical camera, `422` invalid mode.
4. Switching back to `simulated` keeps the synced world state.

### Tests (with `httpx.MockTransport`; no device needed)

- Count 7 → one observation with `source = "physical"` and `waiting_count = 7`, and exactly 7 waiting agents at that stop.
- Count lower than the simulated waiting removes the most recent agents.
- Timeout → no observation and a warning. No observation for that camera while the device stays down.
- Display payloads are forwarded to `/display`.
- Mode errors return `404`, `409` and `422` as specified.
- Switching back and forth keeps passenger conservation.

### Acceptance

```powershell
cd backend
uv run pytest tests/sim -k physical    # green
```

Manual check: run the E1 mock, switch the camera with `POST /sim/cameras/{camera_id}/mode {"mode": "physical"}`, change the mock count, and see `/sim/truth` follow it.

### Demo

The mock (later the Arduino) drives the waiting count of one stop live.

---

## S6 - Synthetic history, 5 weeks

- **Priority:** P1
- **Status:** todo
- **Depends on:** S4

### Objective

Extend S4 to 5 weeks (2026-09-07 to 2026-10-11) with a train and test split.

### Instructions

- `generate-history --weeks 5` writes the same files, plus `data/history/split.json` with `{train: [2026-09-07, 2026-10-04], test: [2026-10-05, 2026-10-11]}`.
- Add a few random `overcrowding` events (about one per day at a random stop) so the history contains anomalies, and record them in truth.
- Budget: generation under 20 minutes. If it is slower, profile and vectorise the arrival generation before reducing the scope.

### Tests

- The split covers all days with no overlap.
- The generator seeds its RNG per day from (seed, date), so generating a single day alone gives the same messages as that day inside the 5-week run.
- Anomaly events appear in truth.

### Acceptance

```powershell
cd backend
uv run python -m app.cli generate-history --weeks 5 --seed 42   # under 20 minutes, split.json written
```

### Demo

Enough history to train the P1 models (K5) and measure calibration on a held-out week (K6).
