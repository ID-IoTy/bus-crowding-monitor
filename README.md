# Bus Crowding Monitor

An independent public-transport prototype combining stop crowd counts and bus occupancy. Public Turin route data provides geography; no transport operator is a project partner.

## Versions and branches

| Branch | Purpose |
| --- | --- |
| `frontend` | Preserved initial three-bus demo at `596f559085c134f471c79c26be38c877b0738751` |
| `frontend-v2-clean-map` | Visual variant with compact colour markers and click-to-open details |
| `frontend-v2` | Four-line, five-bus frontend with live/forecast maps and measured synthetic evaluation |
| `backend` | Colleague's FastAPI server in `server/` |
| `Arduino` | Colleague's UNO Q counting application in `arduino/` |
| `integration` | Integration workspace created from `main`; components are brought together through PRs |
| `main` | Shared documentation, then verified integrated milestones |

The initial demo remains recoverable from its branch and exact commit. The planned `v0.1.0-demo` tag/release has not yet been created: the connected GitHub tool does not expose release/tag creation, and the available browser is signed out. Do not move the preserved branch or rewrite its history. See [versioning](docs/VERSIONING.md).

## Clean-map variation

The `frontend-v2-clean-map` branch preserves the original v2 and adds a quieter map. Bus markers show only the line number; stop markers are 10px dots with 24px interactive targets. Click, tap or keyboard activation opens counts, timestamps and forecast details. Stop details are not pre-opened on initial load. The original bus brand icon is restored and decorative 33/42 sidebar badges are removed.

Bus details and passenger cards emphasize occupied **total-capacity percentage**; raw counts remain available in details. Map colours are green below 40%, yellow from 40% to below 60%, orange from 60% to below 85%, and red from 85%. Grey indicates old or missing observations. For stops these percentages use illustrative demo thresholds, not measured physical capacity. In forecast mode only stop colours become forecasts; buses retain their latest observations and current simulated positions. The visual bands do not change the three calibrated forecast categories or prediction model.

Integration remains deferred.

## Frontend v2

- **Live map:** all lines and directions visible; one marker per physical stop ID; latest observed stop counts and current simulated bus positions.
- **Forecast map:** stop crowd forecasts at +5, +10 and +15 minutes, based on recent observations and synthetic historical patterns.
- **Stop detail:** click, keyboard activation, tap, or an accessible stop selector reveals observations, timestamps, forecasts and reliability.
- **Passenger comparison:** highlight the soonest and least crowded bus among those serving both departure and destination in the correct direction. No automatic choice and no transfers.
- **Operator-only history:** seven historical days, stop/line/direction/day filters, crowded stop-minutes, capacity-pressure estimates, missing/stale readings and model quality.
- **Fleet:** two line 18 buses toward Piazza Sofia, one line 68 toward Via Cafasso, one line 33 toward Collegno and one line 42 toward Ospedale Martini. Return patterns are visible without a simulated fleet.
- Shared stops have one queue. Private simulated passenger destinations determine compatible boarding; the predictor never receives these destinations.

### Run

Node.js 22.18+ or 24 is required (verified with 24.14).

```powershell
# Check out frontend-v2-clean-map for this variation, then:
cd frontend
npm ci
npm run dev
```

Open the port printed by Vite, normally `http://127.0.0.1:5173/`.
Passenger view: `/#citizens`; operator view: `/#operators`.

```powershell
npm test
npm run build
```

The first scenario prepares three independent synthetic weeks in a Web Worker (approximately 10–20 seconds on the development machine). Subsequent switches to an already prepared scenario reuse the model in that tab. UI polling every five seconds advances simulation by thirty seconds. Pause and reset are available. Separate browser tabs have independent simulation state.

## Observations, predictions and interpretation

The device workstream counts people present, not confirmed boardings or alightings. Bus counts are expected at departure; stop counts are periodic and, when arrival triggers exist, before arrival and shortly after departure. The simulator implements these triggers; current hardware support must be checked independently.

Counts alone cannot establish exact boarding/alighting, individual destinations, or abandonment. A drop in a queue is not evidence that people left because of delay. Total onboard counts do not reveal free seats.

Demo vehicle capacity is 75 including 32 seats. Stop capacities are illustrative: 30, or 60 for shared 33/42 stops. Busy begins at 60%; very busy at 85%. These are not verified physical or safety limits.

The predictor combines a historical time profile with the residual from the latest stop count and estimated effects of approaching buses. Bus forecasts use historical positive/negative net onboard changes and observed demand. All are demonstration estimates, not field-validated ML results. Observations older than two simulated minutes are marked stale; missing readings never become fresh zeroes.

Reliability means the measured frequency of a correct crowd category in a comparable synthetic calibration group, separated by entity type, horizon and predicted category. It is shown only with at least 30 examples. A third independent week evaluates performance without tuning the model. Overall scores and per-category calibration/test results appear in the operator view. Historical-only forecasts have no reliability percentage. Arbitrary bus-arrival ETAs are not assigned percentages calibrated only at fixed 5/10/15-minute horizons.

## Backend and Arduino integration

Integration is deferred for now. The `integration` branch has been created, but no component branches have been merged into it. Frontend v2 is delivered independently on `frontend-v2`.

The backend already exists in the colleague's `backend` branch. Arduino already has an HTTP reporter using `POST /ingest/stop-event` and `POST /ingest/bus-event` with `X-API-Key`.

The v2 frontend uses an adapter and a standalone synthetic model. It is not yet a production API client. See [API integration contract and gaps](docs/API_CONTRACT.md).

The current backend uses synthetic IDs such as `R1-S05` and associates each stop with one route. The frontend uses GTFS stop IDs shared across routes. These IDs must not be silently mapped by name or array index. A shared physical-stop/route-pattern model, observation timestamps, fixed-horizon stop forecasts and calibrated reliability require further backend coordination.

Integrate component code and verify a minimal observed-count path first. Preserve the standalone demo as a fallback. Do not label simulated counts, synthetic schedules or inferred quantities as live operator data.

## Data provenance and validation

The bundled fixture uses static GTFS feed `20261009`, declaring service dates 2026-10-08 through 2027-01-31. Source: [public GTFS archive](https://www.gtt.to.it/open_data/gtt_gtfs.zip). The importer selects one common complete trip pattern per direction; it omits variants. It reads routes, stops, trips, stop ordering and shapes. No live vehicle positions, passenger counts or official ETA predictions were imported.

| Line | Direction 0 stops | Direction 1 stops |
| --- | ---: | ---: |
| 18 | 50 | 50 |
| 68 | 41 | 40 |
| 33 | 41 | 41 |
| 42 | 31 | 27 |

The full GTFS ZIP is not committed. Confirm reuse terms before public redistribution. Map tiles use OpenStreetMap attribution; tiles and optional fonts need network access.

The Politecnico paper, *A low-cost automatic people-counting system at bus stops using Wi-Fi probe requests and deep learning* ([DOI](https://doi.org/10.1007/s12469-023-00349-0)), is methodological background. It uses Wi-Fi, not video, and reports approximately 1.2-person MAE for a five-minute occupancy estimate. Its dataset is not public. Its result is not the accuracy of this prototype. No video benchmark or field validation has been performed here.

## Decision record

- 2026-10-10: React/TypeScript frontend, colleague-owned FastAPI backend and Arduino UNO Q counting workstream; independent passenger/operator views; initial 18/68 demo delivered.
- 2026-10-11: Preserve the initial frontend; develop on `frontend-v2`; integrate through `integration` and PRs, keeping colleagues' branch history.
- 2026-10-11: Add 33/42, one bus each; all lines visible; separate live/forecast maps; shared physical-stop counts; destination-compatible passenger comparison.
- 2026-10-11: History visible only in operator UI for this demo; server authentication is a future access-control requirement.
- 2026-10-11: Evaluate synthetic forecasts with independent training, calibration and test weeks; label all reliability as synthetic.
- 2026-10-11: Finish and publish frontend v2 independently; postpone backend and Arduino integration until a later project phase.

## Remaining work

- Complete the minimal backend-to-frontend connection and test Arduino reporter interoperability.
- Agree shared-stop topology and actual frontend/backend forecast contracts before migrating the network.
- Support measured observation times, unique event/visit IDs, idempotent retries and persistent operator acknowledgements.
- Add real data validation and device arrival/departure triggers.
- Tag/release the preserved first demo when a release-capable authenticated interface is available.
