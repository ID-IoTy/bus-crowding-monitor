# Bus Crowding Monitor

A smart public transport prototype combining bus occupancy and stop crowd counts, with a passenger web app and an operator dashboard.

**Delivery target:** October 11, 2026, 16:00 Europe/Rome.  
**Runtime:** localhost for the initial demo.  
**Stack:** Python/FastAPI backend; React/TypeScript frontend.

## Status and team responsibilities

| Component | Owner | Status |
| --- | --- | --- |
| Central server, ingestion, correlation, predictions, and output APIs | Backend colleague | Specification agreed; implementation and API contracts to be supplied by the colleague |
| Passenger web app and operator dashboard | Frontend workstream | Initial implementation in progress on the `frontend` branch, using explicitly labelled mock data |
| Stop counting and device-side processing | Hardware colleague | Separate workstream using an Arduino UNO Q with 4 GB RAM |
| Shared project documentation | Team | Maintained on `main` and kept aligned with implementation |

The project includes both frontend interfaces. The backend colleague's specification is backend-only: it does not remove either interface from the overall project.

## Agreed demo scope

- Two complete real GTT bus lines in Turin; treat each line independently, without transfers.
- A simulated or manually selected passenger origin.
- The initial stop is the closest stop to that origin; the passenger selects the destination.
- Display crowding along a valid same-line route in the appropriate direction.
- Consider both seated capacity and total vehicle capacity.
- Use controllable normal-service, rush-hour, and overcrowding scenarios.
- Provide seven days of synthetic historical data.
- Run the backend and web interfaces locally; sharing links with other devices is deferred.
- Keep the architecture extensible to additional lines, stops, vehicles, data sources, and future routing complexity.

Real public route geography is the target. Bus movements, passenger counts, and initial predictions are demonstration data until their respective integrations are available. Any provisional route fixture must be labelled as such.

## Central server specification

The backend is implemented by a separate colleague. The following requirements are the agreed foundation for that workstream.

### Inputs

**Bus APC (Automatic Passenger Counting)**

At door closure and departure from a stop, the server receives the onboard passenger count and the stop ID, together with the available APC event information.

Vehicle, line, direction, trip, measurement time, and event identifiers must be agreed in the ingestion contract. A stop ID alone cannot identify which bus visit an event describes.

**Smart bus stop camera and sensors**

The stop sends its ID and the number of people currently waiting:

- Every 60 seconds.
- Immediately before or when a bus arrives.
- After a bus departs, following a short delay to let alighting passengers leave the counting area; approximately 10 seconds is the initial example, not a validated setting.

The team still needs to agree how bus arrival/departure events trigger these additional observations and how each observation references the corresponding visit.

### Storage and event correlation

The server receives and stores observations, retaining measurement times and data provenance. It correlates the bus departure event with stop observations before arrival and after departure.

Example:

| Observation | Waiting at stop | Onboard bus |
| --- | --- | --- |
| Before arrival | 9 | 19 |
| After departure | 4 | 24 |
| Net change | −5 | +5 |

This is consistent with five people boarding, but counts alone do not uniquely determine boarding and alighting. Other passengers may arrive, leave, board, or alight during the observation interval.

```text
onboard_after = onboard_before + boardings − alightings
waiting_after = waiting_before − boardings + new_arrivals − departures_from_queue
```

The second equation assumes alighting passengers have already left the counted area. The backend must distinguish observed net changes from estimated passenger movements.

### Prediction and anomaly engine

Using current and historical observations, the backend will provide:

- **Future occupancy:** estimated crowdedness of a bus at upcoming stops and along its remaining path.
- **Adjusted ETA and dwell time:** estimates of additional stop time caused by boarding demand, integrated with the existing arrival-time source.
- **Crowd anomalies:** unusual waiting counts or persistence of overcrowding.
- **Possible abandonment:** unusual decreases in waiting counts that may suggest passengers leaving, with the inference clearly identified.
- **Operator recommendations:** capacity concerns and suggestions to consider additional services.

Initial prediction logic may use transparent rules or statistical mocks. No validated accuracy or trained model is currently claimed.

ETA correction must account for dwell time already included in the baseline source. Do not add a full predicted dwell time if a baseline dwell estimate has already been included.

Crowd decreases alone cannot establish that passengers abandoned the stop because a bus was late or full.

### Output APIs

The backend will expose APIs for the passenger app, the operator dashboard, and future physical stop displays.

A request for a stop ID should return:

- The upcoming buses and their adjusted ETAs.
- Predicted crowdedness when each bus reaches that stop.
- Available occupancy predictions along the bus route.
- Observation/prediction times and source information sufficient to distinguish current readings from estimates.

Operator endpoints must additionally support alerts, acknowledgement, and historical statistics.

Endpoint paths, payloads, units, error responses, freshness rules, and prediction uncertainty remain to be agreed with the backend colleague. Frontend types describe its view models; they are not an approved server wire contract.

## Passenger web app

The passenger interface is designed for smartphones:

1. Choose or use a simulated starting position.
2. Identify the nearest initial stop.
3. Select a reachable destination on the same line.
4. View buses and stops on a map.
5. Inspect current waiting counts, current bus occupancy, and server-provided predicted occupancy and adjusted ETA when available.

A journey that requires a transfer or cannot be served in the selected direction must be explained rather than displayed as valid.

Route optimization and fastest-path recommendations remain deferred. Backend occupancy forecasts are now in scope, but they do not imply that the frontend selects a better route.

## Operator dashboard

### Critical situations and interventions

The main view prioritizes stop capacity concerns, crowd anomalies, and backend-generated recommendations. Each alert shows its location, supporting measurements, and whether its values are observed or predicted.

The operator can acknowledge an alert. Acknowledgement records that someone has taken ownership; it does not solve the underlying capacity concern. Alerts resolve when the backend detects recovery.

The interface may suggest considering an additional service. It does not dispatch buses automatically.

### Historical analysis

The calmer monitoring view provides:

- Average and peak bus occupancy.
- Average and peak waiting counts by stop and time of day.
- Comparisons across days and time periods.
- Recurring capacity concerns and alert duration.
- Detail views for lines, vehicles, and stops.

### Supporting map

The operator can also inspect bus and stop locations. Maps remain the primary part of the passenger experience.

## Measurements, capacity, and data limitations

Available measurements are snapshots of people present. Separate boarding and alighting counts have not been confirmed.

For a vehicle with known capacity:

```text
occupancy_percentage = onboard_people / total_capacity × 100
remaining_capacity = max(total_capacity − onboard_people, 0)
people_above_seated_capacity = max(onboard_people − seated_capacity, 0)
```

Total capacity must be positive. The last measure does not directly establish standing passengers or free seats.

A simple current capacity concern is:

```text
estimated_excess_demand = max(waiting_people − remaining_capacity_of_relevant_bus, 0)
```

The estimate ignores unobserved alighting and new demand before arrival. At shared stops, the waiting count does not identify passengers' intended lines and must not silently be assigned to every bus.

Do not sum repeated snapshots and call the result unique passengers or passenger throughput. Missing or stale observations are unavailable data, not zero people.

## Architecture and integration boundary

```text
Bus APC departure events ───────┐
                               ├─> Central backend (colleague)
Stop sensors / Arduino ────────┘      │
                                     ├─ Storage and visit correlation
Simulation and historical fixtures ─>├─ Occupancy, dwell and ETA estimates
                                     ├─ Anomalies and operator alerts
                                     └─ Output APIs
                                           │
                                ┌──────────┼───────────┐
                                v          v           v
                          Passenger    Operator     Future stop
                           web app     dashboard      displays
```

Frontend data access should remain behind an adapter. Local mock data lets UI development continue before the backend APIs are finalized. Replacing the adapter with real API requests must preserve the distinction between observed, predicted, and simulated values.

The database and backend implementation choices beyond Python/FastAPI belong to the backend workstream. No backend application is implemented in the frontend branch.

## Public data, simulation, and validation

The candidate geography source is the [GTT GTFS archive](https://www.gtt.to.it/open_data/gtt_gtfs.zip), with additional context on [Muoversi a Torino open data](https://ls.muoversiatorino.it/it/open-data/).

Route contents, freshness, coverage, and applicable reuse terms must be checked before importing and redistributing a fixture. Static geography does not establish availability of live occupancy data.

Demo scenarios must be reproducible, visibly labelled, and consistent across the map, stop details, charts, and alerts. Seven days of synthetic history are planned.

Field validation is outside the hackathon schedule. Public datasets and papers may inform model assumptions and comparison scenarios. Specific references have not yet been selected. Synthetic tests cannot prove physical counter accuracy or real-world prediction accuracy.

## Development and version control

- Shared project overview: `README.md` on `main`.
- Frontend code: `frontend` branch.
- Backend colleague: independent workstream; their branch is chosen by them.
- Coordinate changes to shared API contracts before connecting either frontend to the server.
- Keep README status, verified startup commands, decisions, and limitations current with each milestone.
- Preserve colleagues' files and commit focused changes.

The frontend is being scaffolded under `frontend/`. Verified installation and startup commands will be documented when the first runnable version is completed.

## Roadmap

- [x] Agree on users, demo scope, and technology.
- [x] Create the repository and confirm GitHub access.
- [x] Create the independent `frontend` branch.
- [x] Adopt the colleague's ingestion, correlation, and prediction specification.
- [ ] Validate and import two complete GTT bus lines.
- [ ] Agree frontend/backend response contracts.
- [ ] Deliver the initial passenger and operator interfaces with mocks.
- [ ] Implement the central backend in the colleague's workstream.
- [ ] Connect real backend responses and reconcile alert state.
- [ ] Prepare historical charts, comparison scenarios, and the demo.
- [ ] Integrate hardware observations.

## Decision record

| Date | Decision |
| --- | --- |
| 2026-10-10 | Separate passenger and operator interfaces with a shared backend. |
| 2026-10-10 | Python/FastAPI backend and React/TypeScript frontend. |
| 2026-10-10 | Two complete real GTT lines, independently navigated without transfers. |
| 2026-10-10 | Simulated origin, nearest initial stop, selected destination, and route crowding. |
| 2026-10-10 | Operator priorities: critical situations, acknowledgement, then analytics. |
| 2026-10-10 | Controlled scenarios, seven synthetic historical days, and localhost delivery. |
| 2026-10-10 | Hardware colleague handles stop counting; backend colleague handles the central server. |
| 2026-10-10 | Add APC departure events, timed stop observations, and visit correlation to the backend specification. |
| 2026-10-10 | Add occupancy forecasts, adjusted ETA/dwell estimates, anomalies, and output for future stop displays. |
| 2026-10-10 | Continue frontend independently using mocks; store frontend code on `frontend`, shared README on `main`. |

## Remaining decisions

- Exact GTT lines, supported directions, and route variants.
- APC payload availability and stop-event synchronization.
- Baseline ETA source and how it already models dwell time.
- API contracts, update cadence, freshness, and uncertainty representation.
- Treatment of shared-stop demand and possible abandonment.
- Fleet sizes, simulation parameters, and vehicle capacities.
- Prediction approach, benchmark references, and alert lifecycle details.
