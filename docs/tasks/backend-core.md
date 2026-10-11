# Backend core (`app/core`) and API

The core behaves as if the sensor data were real:

- it ingests APC events and camera observations through `IngestPort`;
- it correlates them into trips and stop visits;
- it trains models on history, fuses history with live counts, predicts crowding with Monte Carlo sampling and raises alerts;
- it serves everything to the frontend.

- **May edit:** `backend/app/core/`, `backend/app/api/` (except `sim_routes.py`), `backend/app/main.py`, the core subcommands in `backend/app/cli.py`, `backend/tests/core/`, `backend/tests/api/`, `backend/tests/integration/`, `data/config/model.yaml`.
- **Must not:**
  - import `app.sim` from `app/core`;
  - read `sim.sqlite`;
  - call `datetime.now()`. The current simulated time comes from a `now()` callable injected at build time.
- **SPEC:**
  - [section 2](../SPEC.md#2-system-architecture) architecture;
  - [section 3](../SPEC.md#3-clock-and-scheduler) scheduler hooks;
  - [section 5](../SPEC.md#5-stop-visit-sequence) sequence;
  - [section 6](../SPEC.md#6-message-contracts-who-sends-what-to-whom) contracts and common rules;
  - [section 7](../SPEC.md#7-data-model) data model;
  - [section 8](../SPEC.md#8-correlation-logic) correlation;
  - [section 9](../SPEC.md#9-models-and-prediction-engine) prediction;
  - [section 10](../SPEC.md#10-alerts-and-insights) alerts.

`app/main.py` and `app/cli.py` are the only modules that import both `app.sim` and `app.core`.

---

## K1 - Ingestion, static data, read API, WebSocket and wiring

- **Priority:** P0
- **Status:** todo
- **Depends on:** C1, S1. The wiring step also needs S2.

### Objective

Store everything the sensors send, serve the observed state of lines, stops and vehicles, push live deltas, and wire the simulator to the core.

### Instructions

1. `app/core/db.py`:
   - SQLAlchemy 2 models for **all** tables of SPEC section 7 (so later tasks do not migrate), created with `create_all` in `server.sqlite`;
   - at startup, delete rows with `dataset = live`.
2. `app/core/static_loader.py`:
   - load `data/gtfs/fixture_33_42.json` into LINE, STOP, ROUTE_STOP and CAMERA (one camera per stop);
   - `STOP.hub` from `sim.yaml`, or shared stops + termini if empty;
   - VEHICLE rows are upserted on the first event of each vehicle, with capacities from config.
3. `app/core/ingest.py`: `IngestService` implements `IngestPort`.
   - Validate with the contract models.
   - Idempotency via primary key: a duplicate returns `duplicate` with no effect.
   - Append to the raw tables with `received_at = now()`.
   - Update an in-memory live state (last position and onboard per vehicle, last observation per stop).
   - Also expose `ingest_batch(messages, dataset)` for K2's replay: same validation, bulk insert in one transaction.
4. `app/core/factory.py`: `build_core(config, now) -> Core` with `.ingest_port`, `.set_camera_port(port)`, `.on_tick()`, `.every_15s()`.
5. API in `app/api/`:
   - `POST /ingest/vehicle/approach`, `/ingest/vehicle/departure`, `/ingest/camera/observation`: `201` new, `200 {"duplicate": true}`, `422` invalid;
   - `GET /api/lines`, `/api/lines/{line_id}`, `/api/stops`, `/api/stops/{stop_id}`, `/api/vehicles`, `/api/vehicles/{vehicle_id}`, with observed values only for now. A waiting count older than 180 s is `UnavailableValue(status="stale")`; no observation at all is `status="missing"`;
   - `GET /api/health` with `sim_time`.
6. `WS /ws/live`: connection manager; collect deltas (`clock`, `vehicles`, `stops`) and push them aggregated at most once per real second, plus a `clock` message every second.
7. **Wiring step** in `app/main.py` lifespan:
   - load config and create `clock = SimClock(config)`;
   - `core = build_core(config, now=clock.now)`, then `sim = build_sim(config, clock=clock, ingest=core.ingest_port)`;
   - `core.set_camera_port(sim.camera_port)`;
   - register `core.on_tick` and `core.every_15s` on the scheduler;
   - start the sim;
   - include all routers.
   Bind to `127.0.0.1` only (AGENTS rule 10).

### Tests

- New message → `201`; the same message again → `200` and no new row; invalid → `422`.
- A stale observation is returned as `null` with `status: "stale"`, never `0`.
- Static counts match the fixture.
- `/api/vehicles` reflects the last departure of each vehicle.
- WebSocket (TestClient): receives a `clock` envelope; with fake time, at most one push per second.
- `tests/test_isolation.py` stays green.
- Integration: app started with TestClient, scheduler run in batch for 10 simulated minutes → `/api/vehicles` lists buses of both lines.

### Acceptance

```powershell
cd backend
uv run pytest tests/core tests/api tests/integration -k "ingest or static or read or ws or wiring"   # green
```

Manual: run the backend, open http://127.0.0.1:8000/api/vehicles twice a few seconds apart and see positions change.

### Demo

With O2: buses of 33 and 42 moving on the dashboard map.

---

## K2 - Correlation, count-requests and history replay

- **Priority:** P0
- **Status:** todo
- **Depends on:** K1, S3

### Objective

Build trips and stop visits from raw events as in SPEC section 8, drive the pre-arrival and post-departure count-requests, and replay the synthetic history.

### Instructions

1. `app/core/correlation.py`:
   - first event of a trip → TRIP row;
   - `approach` → open STOP_VISIT and `CameraPort.count_request(pre_arrival, delay_s=0)`;
   - the pre-arrival observation is linked by `request_id` / `visit_id`;
   - `departure` → close the bus side, set `departed_full`, update `TRIP.delay_s`, then `count_request(post_departure, delay_s=10)`;
   - post-departure observation → `residual`, `left_behind_est` (formula in SPEC section 8);
   - terminus → `terminus_drift`, trip end, onboard reset;
   - missing or stale pre or post count → `status = incomplete`.
2. `left_behind_est` needs π̂, p_L and λ̂_tot. Read them through a `ModelProvider` interface. Until K3, it returns the fallback priors of SPEC section 9.
3. `app/core/replay.py` and the CLI subcommand `replay ../data/history`:
   - load the JSONL through `ingest_batch` with `dataset = history`;
   - run correlation in batch, without issuing count-requests, because observations already carry their `visit_id`;
   - running it twice adds nothing.

### Tests

- **Integration, one full trip** (sim + core wired in-process, batch mode):
  - one visit per stop;
  - every visit has a pre and a post count;
  - `boarded`, `alighted` and `onboard_after` copied correctly;
  - `terminus_drift` = declared onboard at the last stop.
- A forced full bus at a single-line stop with 20 people waiting → `departed_full` and `left_behind_est > 5`. A bus with free places → `left_behind_est = 0`.
- At a shared stop, people waiting for the other line are not counted as left behind.
- Missing post-departure observation → `incomplete`.
- Replay of 1 simulated day is idempotent.

### Acceptance

```powershell
cd backend
uv run pytest tests/core tests/integration -k "correlation or replay"   # green
uv run python -m app.cli replay ../data/history                          # 1 week in under 2 minutes; prints visits per line and the share of incomplete visits (< 5%)
```

### Demo

`GET /api/stops/{stop_id}` shows the last visit with counts before and after the bus.

---

## K3 - Average models, prediction engine and stop display

- **Priority:** P0
- **Status:** todo
- **Depends on:** K2, S4

### Objective

Predictions with calibrated confidence, as in SPEC section 9, exposed on the API and the WebSocket and sent to the stop displays.

### Instructions

1. `app/core/models/average.py`:
   - train λ̂, σ²_model, α̂, p_L with Var(p_L), π̂ and the waiting profile from `dataset = history` rows, with the estimators of SPEC section 9;
   - write MODEL_STAT with `model_version = "v0.1"`;
   - `ModelProvider` reads MODEL_STAT, with the SPEC fallbacks for empty buckets;
   - online share update after each complete live visit with free capacity.
2. CLI subcommands:
   - `train`;
   - `bootstrap --weeks N`: check the fixture, `generate-history`, `replay`, `train`, in that order.
3. `app/core/prediction.py`:
   - ETA;
   - μ_h, live term, fusion;
   - Monte Carlo propagation with N = 500, numpy-vectorised over samples, RNG seeded from (trip_id, generated_at);
   - per-sample levels with Red precedence, mode, confidence, p_red, interval_80, may_not_fit, stop level.
4. Recompute:
   - trips marked dirty by ingestion at `on_tick`;
   - all active trips at `every_15s`;
   - store the latest PREDICTION per (trip, stop) and one sampled row per trip, stop and minute;
   - push WS `predictions` and `stops` deltas.
5. Display: after each post-departure observation and at every 15 s recompute, build the `DisplayPayload` for that stop (next bus of each line, O' at departure from that stop) and call `CameraPort.display`.
6. Extend `/api/stops*` and `/api/vehicles*` with next buses, predictions and stop level, as in the `GET /api/stops/{stop_id}` example. `/api/health` returns `model_version`.

### Tests

- **Worked example** of SPEC section 9 reproduced from its inputs:
  - μ = 11.7 ± 0.1, σ² = 6.69 ± 0.05;
  - level yellow, confidence 0.69 ± 0.05, interval_80 [70, 79] ± 1;
  - stop level green.
- Stale camera → μ = 10, σ² = 16. No observation → same.
- Capacity: demand far above free places → B = free places, level red, `may_not_fit = true`. Red wins over orange.
- Confidence (fixed seed) decreases with the number of stops ahead.
- A count jump at a downstream stop moves μ towards the count within one recompute.
- Training on 1 simulated day of history gives λ̂ within 25% of the configured base rate at non-peak, non-hub stops.
- Performance: full recompute for 20 trips × 25 stops in under 200 ms.

### Acceptance

```powershell
cd backend
uv run pytest tests/core -k "models or prediction or display"   # green
uv run python -m app.cli bootstrap --weeks 1                    # completes; prints model_version v0.1 and MODEL_STAT row counts per kind
```

### Demo

The map colours stops and buses by predicted level. The detail panel shows confidence and interval_80 changing as new counts arrive.

---

## K4 - Alerts (P0 set) and lifecycle

- **Priority:** P0
- **Status:** todo
- **Depends on:** K3

### Objective

The four P0 alerts of SPEC section 10, with evidence, deduplication and the open → acknowledged → resolved lifecycle.

### Instructions

1. `app/core/alerts.py`, with rules evaluated after each relevant event and at every 15 s tick:
   - CAPACITY_RISK;
   - LEFT_BEHIND;
   - CROWD_ANOMALY;
   - SENSOR_STALE.
   Open and resolve thresholds come from `model.yaml`.
2. Deduplication: at most one open or acknowledged alert per (type, stop_id, line_id, trip_id). A repeated trigger updates the evidence.
3. Evidence JSON: the values used, each with `kind`, timestamps and `model_version`.
4. Endpoints and push:
   - `GET /api/operator/alerts?state=&severity=`, sorted by severity then age;
   - `POST /api/operator/alerts/{alert_id}/ack`: `404` unknown, `409` if already resolved;
   - WS `alerts` delta on open, update and state change.

### Tests

One dedicated fixture or scenario per alert type triggers it and then resolves it:

- CAPACITY_RISK with forced high demand;
- LEFT_BEHIND with a full bus and residual;
- CROWD_ANOMALY with `overcrowding`;
- SENSOR_STALE with a camera silent for 180 s.

Also:

- Deduplication: the same condition twice gives one alert.
- Lifecycle: ack moves open → acknowledged; the condition clearing moves it to resolved; ack on resolved → `409`.
- Evidence contains `kind` for every value.
- Integration: `rush_hour`, batch mode, 30 simulated minutes → at least one CAPACITY_RISK on the shared section.

### Acceptance

```powershell
cd backend
uv run pytest tests/core tests/integration -k alerts   # green
```

### Demo

Steps 4 and 6 of the demo script: an alert appears with evidence, is acknowledged and later resolves by itself.

---

## K5 - HistGradientBoosting models

- **Priority:** P1
- **Status:** todo
- **Depends on:** K3, S6

### Objective

Replace the λ and α averages with scikit-learn HistGradientBoosting models, only if they beat the averages on the test week.

### Instructions

- **Features:** stop, line, direction, hour, minute of the hour, day_type.
  - λ: Poisson loss on `boarded` with `gap_L` as exposure (predict rate × gap).
  - α: squared loss on `alighted / onboard_before`.
- Train on the train split of `split.json`. Evaluate MAE of predicted boarded and alighted on the test week against the v0.1 averages.
- Save to `backend/artifacts/v0.2/` with joblib, `model_version = "v0.2"`.
- `ModelProvider` uses v0.2 only if its MAE is lower. Otherwise keep v0.1 and log the reason.

### Tests

- The training is deterministic with a fixed seed.
- The artifact loads and predicts.
- The provider falls back to v0.1 when told v0.2 is worse.

### Acceptance

```powershell
cd backend
uv run python -m app.cli train --model hgb   # prints MAE v0.1 vs v0.2 on the test week, and the version in use
```

### Demo

`/api/health` shows the model version in use. The evaluation table can be shown in the pitch.

---

## K6 - Calibration, insights and history endpoints

- **Priority:** P1
- **Status:** todo
- **Depends on:** K5

### Objective

Prove that "70% confidence" means about 70% correct, and give the operator analytics on system flaws.

### Instructions

1. CLI subcommand `evaluate`:
   - run the core in batch over the test week, using only data available at issue time;
   - issue predictions once per simulated minute for each active trip and its downstream stops;
   - compare each with the level computed from the observed `onboard_after` and `left_behind_est` of the visit;
   - store the results.
2. `GET /api/operator/calibration`: per 0.1 confidence bucket, mean confidence, observed hit rate and count. Also report the overall Brier score.
3. `GET /api/operator/insights`, all from `server.sqlite`:
   - lost demand by stop and hour, with lost fares (fare in `model.yaml`, default €1.90);
   - chronic overcrowding;
   - recurring bunching;
   - APC drift per vehicle;
   - camera reliability.
4. `GET /api/operator/history?stop_id=&line_id=&from=&to=&bucket=hour`: mean and peak occupancy and waiting.

### Tests

- Hit rate is computed correctly on a synthetic table.
- Buckets with fewer than 30 predictions are flagged.
- Insights on a fixture with known left-behind give the expected totals.

### Acceptance

```powershell
cd backend
uv run python -m app.cli evaluate   # prints the reliability table; every bucket with ≥ 30 predictions within ±10 points (if not, record the result honestly in the README)
```

### Demo

O6 shows the reliability chart and the lost-demand ranking.

---

## K7 - Alerts (P1 set)

- **Priority:** P1
- **Status:** todo
- **Depends on:** K4

### Objective

Add the four P1 alerts of SPEC section 10 to the alert engine.

### Instructions

Add BUNCHING, APC_DRIFT, POSSIBLE_ABANDONMENT and DATA_INCONSISTENCY to the same engine, with the same deduplication and lifecycle. POSSIBLE_ABANDONMENT evidence says `"inference": true`.

### Tests

One dedicated fixture per type triggers and resolves it.

### Acceptance

```powershell
cd backend
uv run pytest tests/core -k alerts   # green, 8 alert types covered
```

### Demo

The alert list shows the full set of SPEC section 10.

---

## K8 - Journey API

- **Priority:** P2
- **Status:** todo
- **Depends on:** K3

### Objective

Serve the citizen app's journey view on top of the existing predictions.

### Instructions

- `GET /api/journey?line=&dir=&from=&to=`: journey stops with ETA, observed waiting and predicted onboard at departure (SPEC example), plus the next buses.
- Same line and direction only. If `to` comes before `from`, or the stops are on different lines, return `422` with a `reason` (`wrong_direction` or `needs_transfer`) and a human-readable explanation.

### Tests

- Valid journey.
- Wrong direction.
- Needs transfer.
- Stale values returned as unavailable.

### Acceptance

```powershell
cd backend
uv run pytest tests/api -k journey   # green
```

### Demo

Z2 shows a journey coloured by predicted level.
