# Bus Crowding Monitor

An independent public-transport prototype combining stop crowd counts and bus occupancy. Public Turin route data provides geography; no transport operator is a project partner.

## Versions and branches

| Branch | Purpose |
| --- | --- |
| `frontend-v3-map-contrast` | Current map: bus labels show only the line; white route casing with a dark outer edge improves contrast |
| `frontend-v3-inline-bus` | Preserved layout: selected bus expands its left-hand card with observed count, after-departure prediction and occupancy percentage |
| `frontend-v3-desktop-fit` | Preserved desktop layout: viewport-sized map and compact controls, one direction's three trips at a time, details in dialogs |
| `frontend-v3-minimal` | Current logo-only interface: no sidebar, introductory header or scenario controls; views selected through URL hashes |
| `frontend` | Preserved initial three-bus demo at `596f559085c134f471c79c26be38c877b0738751` |
| `frontend-v3-journey` | Current stop-first passenger planner: optional destination/date, three scheduled services and after-departure forecasts |
| `frontend-v3-side-map` | Current layout variation: journey search, cards and details on the left; persistent map on the right |
| `frontend-v2-capacity-70` | Preserved clean-map iteration at `536b3d0022264125434b4603406282776bee7395` |
| `frontend-v2-clean-map` | Visual variant with compact colour markers and click-to-open details |
| `frontend-v2` | Four-line, five-bus frontend with live/forecast maps and measured synthetic evaluation |
| `backend` | Colleague's FastAPI server in `server/` |
| `Arduino` | Colleague's UNO Q counting application in `arduino/` |
| `integration` | Integration workspace created from `main`; components are brought together through PRs |
| `main` | Shared documentation, then verified integrated milestones |

The initial demo remains recoverable from its branch and exact commit. The planned `v0.1.0-demo` tag/release has not yet been created: the connected GitHub tool does not expose release/tag creation, and the available browser is signed out. Do not move the preserved branch or rewrite its history. See [versioning](docs/VERSIONING.md).

## Passenger journey iteration

Choose a departure stop by name, code or zooming into the map. Destination is optional: when provided, only direct services reaching it after departure in the same direction appear. Date/time is optional and interpreted in Europe/Rome; **Now** uses the simulated clock. Future dates are supported. No transfers are planned.

The `frontend-v3-side-map` variation places search, route options and selected bus/stop details in a left column, with a sticky map on the right. At viewport widths of 760px or less the columns stack vertically. The original `frontend-v3-journey` remains preserved at `5dda674b54e005ec369ab3754fcc974fef028a58`.

The `frontend-v3-minimal` iteration retains that layout while removing the sidebar, interface buttons, introductory text, clock header, fleet badge and scenario/Pause/Reset toolbar. Only the Transit logo remains above the workspace. Open `/#citizens` for the passenger app or `/#operators` for the control room; URL hash changes switch views. The normal scenario runs automatically, advancing the simulated clock as before. The optional journey time field and Now action remain available. The previous side-map layout is preserved at `31461bc1e824c7e96990e3e532b96840db537b58`.

The `frontend-v3-desktop-fit` iteration sizes the passenger workspace to the desktop window, compacts the search fields and displays three trips for one direction at a time. A line/direction selector exposes every compatible option without stacking cards down the left column. Selecting a bus or stop opens a dismissible detail dialog; About demo retains the synthetic-service explanation without adding page height. Small screens retain a vertical, scrollable layout. The previous minimal shell is preserved at `e2c80029697bfc3b1f77d48610de00ef9250579a`.

The `frontend-v3-inline-bus` variation expands the selected trip inside the left column instead of opening a bus dialog. Its three metrics are **Currently on bus**, **Predicted after departure** and **Percentage**, with observation/departure timestamps. Percentages omit the approximation symbol; they remain synthetic predictions, not calibrated measurements. On desktop the search fields collapse during bus selection; **Edit journey** restores them. The other two trips remain visible. Stop and demo-information dialogs remain available. The previous desktop-fit iteration is preserved at `45783509036c1ae330c5e15bc7b9d4b02245aa57`.

The `frontend-v3-map-contrast` variation removes trip ordinal suffixes from bus markers. Route colours retain their occupancy meaning and gain a white casing with a dark outer edge for readability against map tiles. Portions outside the selected journey remain attenuated. Trip identity and selection remain distinct even when marker labels match. The previous inline-bus version is preserved at `d63896fe6282903e142ec6a1bc19ec97916941dc`.

Each compatible direction offers three distinct scheduled trips. Cards show arrival time, destination arrival when requested, and predicted occupancy **after leaving your stop**, rather than occupancy before boarding. Click a card or a bus marker for the same inline observed count, after-departure estimate and boarding concerns. The demo assumes 70 total places; unknown capacity produces no occupancy percentage. Reliability is unavailable because this new target has not been calibrated.

Selecting a direction isolates and fits its full route. A continuous colour interpolation follows the actual route shape using mean after-departure forecasts from the displayed trips; selecting a trip switches to its own forecasts. Past/unavailable forecasts are grey. Optional origin-to-destination travel is emphasized and the rest attenuated. Stop dots appear at zoom 15; selected endpoints remain visible. Stop details offer **Start here** and **Set destination**. Labels for nearby buses are offset so all remain selectable; future/not-started positions are explicitly labelled.

The passenger planner uses a new deterministic **synthetic scheduled service**, not the transport operator's timetable: every 10 minutes, 24 hours/day, all eight imported directions, three minutes travel and 30 seconds dwell per stop. It combines hand-authored historical demand profiles with recent synthetic stop observations; it is not trained ML. See [passenger model and handoff](docs/PASSENGER_JOURNEY.md) for exact assumptions and interfaces.

The control room retains the v2 five-bus simulation and its existing evaluation. The two demos share scenario and clock controls, **not a common fleet or count dataset**. Its calibration scores do not validate the new passenger predictions. Unifying both views with the colleague's backend is deferred; no backend/Arduino code has been merged.

The v2 sections below describe that preserved control-room model and earlier passenger screen, not the new planner.

## Clean-map variation (v2)

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
# Check out frontend-v3-map-contrast for this iteration, then:
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

The model prepares three independent synthetic weeks in a Web Worker (approximately 10–20 seconds on the development machine). UI polling every five seconds advances simulation by thirty seconds. The minimal shell runs the normal scenario automatically; scenario, pause and reset controls remain available in earlier iterations. Separate browser tabs have independent simulation state.

## Observations, predictions and interpretation

The device workstream counts people present, not confirmed boardings or alightings. Bus counts are expected at departure; stop counts are periodic and, when arrival triggers exist, before arrival and shortly after departure. The simulator implements these triggers; current hardware support must be checked independently.

Counts alone cannot establish exact boarding/alighting, individual destinations, or abandonment. A drop in a queue is not evidence that people left because of delay. Total onboard counts do not reveal free seats.

All five demo buses have 70 total passenger places, including 25 seats (45 standing places); the driver is excluded. This is a uniform synthetic configuration, not a verified assignment or specification for these real routes. Stop capacities are illustrative: 30, or 60 for shared 33/42 stops. Busy begins at 60%; very busy at 85%. These are not verified physical or safety limits.

The predictor combines a historical time profile with the residual from the latest stop count and estimated effects of approaching buses. Bus forecasts use historical positive/negative net onboard changes and observed demand. All are demonstration estimates, not field-validated ML results. Observations older than two simulated minutes are marked stale; missing readings never become fresh zeroes.

Reliability means the measured frequency of a correct crowd category in a comparable synthetic calibration group, separated by entity type, horizon and predicted category. It is shown only with at least 30 examples. A third independent week evaluates performance without tuning the model. Overall scores and per-category calibration/test results appear in the operator view. Historical-only forecasts have no reliability percentage. Arbitrary bus-arrival ETAs are not assigned percentages calibrated only at fixed 5/10/15-minute horizons.

## Backend and Arduino integration

Integration is deferred for now. The `integration` branch has been created, but no component branches have been merged into it. The current standalone passenger iteration is delivered on `frontend-v3-journey`; earlier frontend branches remain recoverable.

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

- 2026-10-11: Publish the uniform 70-total / 25-seated fleet on `frontend-v2-capacity-70`, preserving previous branches and their exact commits. Stop-demand changes remain pending; this iteration changes bus capacity only.

## Remaining work

- Complete the minimal backend-to-frontend connection and test Arduino reporter interoperability.
- Agree shared-stop topology and actual frontend/backend forecast contracts before migrating the network.
- Support measured observation times, unique event/visit IDs, idempotent retries and persistent operator acknowledgements.
- Add real data validation and device arrival/departure triggers.
- Tag/release the preserved first demo when a release-capable authenticated interface is available.
