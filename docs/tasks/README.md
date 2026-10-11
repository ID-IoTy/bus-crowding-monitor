# Tasks per system

Each file is assignable on its own to one person or one AI agent. Rules, commands and Definition of Done are in [`AGENTS.md`](../../AGENTS.md); the design is in [`SPEC.md`](../SPEC.md).

| File | System | Folders it may edit | Tasks |
| --- | --- | --- | --- |
| [`contracts.md`](contracts.md) | Contracts and repo skeleton | `backend/` (skeleton, `app/contracts`, `app/main.py`), `scripts/`, `data/config/` | C1 |
| [`backend-sim.md`](backend-sim.md) | Simulator | `backend/app/sim`, `backend/app/api/sim_routes.py`, sim subcommands in `backend/app/cli.py`, `backend/tests/sim`, `data/gtfs`, `data/scenarios`, `data/config/sim.yaml` | S1-S6 |
| [`backend-core.md`](backend-core.md) | Core | `backend/app/core`, `backend/app/api` (except `sim_routes.py`), `backend/app/main.py`, core subcommands in `backend/app/cli.py`, `backend/tests/core`, `backend/tests/api`, `backend/tests/integration`, `data/config/model.yaml` | K1-K8 |
| [`frontend-operator.md`](frontend-operator.md) | Operator dashboard | `frontend/` (except `src/citizen`), `scripts/dev.ps1` | O1-O6 |
| [`frontend-citizen.md`](frontend-citizen.md) | Citizen app | `frontend/src/citizen` | Z1-Z3 |
| [`edge.md`](edge.md) | Arduino UNO Q and its mock | `edge/` | E1-E5 |

## Priorities

- **P0:** the demo of [SPEC section 1](../SPEC.md#demo-script-p0). Must be done.
- **P1:** enrichment. Start only when the P0 tasks of the same system are done or blocked.
- **P2:** later.

## Dependency graph

```mermaid
flowchart TD
  C1["C1 contracts"]
  S1["S1 GTFS import"]
  S2["S2 clock + buses"]
  S3["S3 passengers, APC, cameras"]
  S4["S4 history 1 week"]
  S5["S5 physical camera mode"]
  S6["S6 history 5 weeks (P1)"]
  K1["K1 ingestion + read API + WS"]
  K2["K2 correlation"]
  K3["K3 prediction"]
  K4["K4 alerts P0"]
  K5["K5 tree models (P1)"]
  K6["K6 calibration + insights (P1)"]
  K7["K7 alerts P1"]
  K8["K8 journey API (P2)"]
  O1["O1 skeleton + adapter"]
  O2["O2 live map"]
  O3["O3 demo control panel"]
  O4["O4 alerts"]
  O5["O5 stop and bus detail"]
  O6["O6 analytics (P1)"]
  Z1["Z1 citizen map (P2)"]
  Z2["Z2 journey (P2)"]
  Z3["Z3 citizen stop detail (P2)"]
  E1["E1 Arduino mock"]
  E2["E2 Arduino HTTP server"]
  E3["E3 on-device counting"]
  E4["E4 basic display"]
  E5["E5 advanced display (P2)"]

  C1 --> S1 --> S2 --> S3 --> S4
  C1 --> K1
  S1 --> K1
  S2 -->|"wiring step"| K1
  K1 --> K2
  S3 --> K2
  S4 --> K3
  K2 --> K3
  K3 --> K4
  C1 --> O1
  O1 --> O2
  K1 --> O2
  O1 --> O3
  S3 --> O3
  S5 -.->|"camera switch"| O3
  O1 --> O4
  K4 --> O4
  O1 --> O5
  K3 --> O5
  C1 --> E1
  E1 --> S5
  S3 --> S5
  E1 --> E2 --> E3
  E2 --> E4
  K3 --> E4
  S4 --> S6
  S6 --> K5
  K3 --> K5
  K5 --> K6
  K4 --> K7
  K6 --> O6
  O1 --> O6
  K3 --> K8
  O1 --> Z1
  K3 --> Z1
  Z1 --> Z2
  K8 --> Z2
  Z1 --> Z3
  E4 --> E5
```

## P0 path

The order gets a first end-to-end slice (buses moving on the dashboard) as early as possible.

1. **C1** contracts and skeleton. Everything depends on it.
2. **S1** GTFS import.
3. In parallel: **S2** clock and buses, **K1** ingestion and read API, **O1** frontend skeleton on mocks, **E1** Arduino mock.
4. **K1 wiring step** + **O2** live map. First demo: buses of 33 and 42 moving at x10 on the dashboard.
5. **S3** passengers, APC and cameras, then **K2** correlation and **S4** history (in parallel), then **K3** prediction and **K4** alerts.
6. **O3**, **O4**, **O5** as the backend pieces land (they can start earlier on mocks).
7. **S5** physical camera mode with the mock, then **E2**, **E3**, **E4** on the real Arduino.
8. Rehearse the demo script, then P1 if time remains.

## Coverage check

Every endpoint and interface of [SPEC section 6](../SPEC.md#6-message-contracts-who-sends-what-to-whom) is owned by a task:

| Endpoint or interface | Task |
| --- | --- |
| Contract models, `IngestPort`, `CameraPort`, ID formats, `GET /api/health`, `GET /api/ws-schema` | C1 |
| `GET /sim/state`, `POST /sim/clock` | S2 |
| `GET /sim/scenarios`, `POST /sim/scenario`, `GET /sim/truth`, `CameraPort` (simulated) | S3 |
| `GET /sim/cameras`, `POST /sim/cameras/{camera_id}/mode`, gateway ↔ Arduino HTTP | S5 |
| `IngestPort`, `POST /ingest/*`, `GET /api/lines*`, `GET /api/stops*`, `GET /api/vehicles*` (observed), `WS /ws/live` | K1 |
| Count-requests through `CameraPort` | K2 |
| Predictions in `/api/stops*`, `/api/vehicles*`, WS `predictions`, `CameraPort.display` | K3 |
| `GET /api/operator/alerts`, `POST /api/operator/alerts/{alert_id}/ack`, WS `alerts` | K4 |
| `GET /api/operator/calibration`, `/api/operator/insights`, `/api/operator/history` | K6 |
| `GET /api/journey` | K8 |
| Arduino `GET /count`, `POST /display` | E1 (mock), E2 (device) |
