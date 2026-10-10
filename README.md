# Bus Crowding Monitor

Bus and stop crowding monitoring system with a passenger web app, an operator dashboard, and a data simulator.

The project combines the number of people waiting at bus stops with vehicle occupancy to help passengers understand crowding along their journey and help transport operators identify potential capacity shortages.

> **Status:** Project definition and documentation. The features below describe the agreed prototype scope; application code and startup commands are not available yet.
>
> **Demo data:** Bus positions, passenger counts, and historical observations will be simulated. Real GTT routes and stops will provide the geographic context once the public dataset has been verified and imported.

## Project goals

- Give passengers a map of buses and stops with current crowding information along their selected route.
- Help operators identify stops where waiting demand may exceed the available capacity of an approaching bus.
- Provide historical charts to compare crowding across stops, vehicles, and time periods.
- Keep hardware ingestion, simulation, processing, and presentation separate so the system can grow beyond the hackathon prototype.

The hackathon delivery target is **October 11, 2026, at 16:00 Europe/Rome**.

## Prototype scope

| Area | Agreed scope |
| --- | --- |
| Transport network | Two complete, real GTT bus lines in Turin; exact lines still to be selected |
| Journey support | Each line is treated independently; no transfers between lines |
| Passenger origin | A simulated or manually selected location |
| Initial stop | The closest stop to the simulated origin |
| Destination | A stop selected by the passenger, reachable on the same line in the relevant direction |
| Vehicle data | Simulated locations and onboard passenger counts |
| Stop data | Simulated waiting-person counts initially; hardware integration later |
| Capacity | Both seated capacity and total passenger capacity |
| Historical data | Seven days of clearly labelled synthetic observations |
| Demo controls | Normal service, rush hour, and overcrowding scenarios, with manual controls |
| Runtime | Backend and both web interfaces on localhost |
| Technology | Python with FastAPI; React with TypeScript |

Two complete lines replace the earlier proposal of a small line segment with a single bus. The number of simulated vehicles and their schedules remain to be defined.

## Passenger web app

A mobile-friendly web interface will let passengers:

1. Set or use a simulated starting position.
2. See the closest initial stop.
3. Select a destination stop supported by the same line and direction.
4. View the relevant route section, stops, and buses on a map.
5. Inspect waiting-person counts at stops and occupancy information for buses.

The first version shows **current crowding along the selected route**. It does not calculate the fastest route, optimize journeys based on crowding, support transfers, or predict occupancy at the passenger's future arrival time.

If the selected destination cannot be reached from the initial stop under these constraints, the interface must explain that limitation rather than display an invalid journey.

## Operator dashboard

The dashboard will prioritize actionable capacity concerns, followed by historical analysis and a supporting map.

### 1. Critical situations and suggested interventions

- Highlight stops where waiting demand exceeds the estimated remaining capacity of the next relevant bus.
- Explain each alert using the stop count, bus occupancy, vehicle capacity, and estimated excess demand.
- Suggest that the operator **consider an additional service**.
- Allow the operator to acknowledge or take ownership of an alert.
- Resolve the alert when the underlying capacity concern clears.

Acknowledging an alert does not mean the capacity problem has been solved. The prototype will not automatically dispatch vehicles or claim to determine an exact fleet allocation.

### 2. Statistics and detailed analysis

- Average and peak vehicle occupancy.
- Average and peak stop crowding by time of day.
- Comparisons between days and time periods.
- Stops with recurring capacity concerns.
- Alert counts and duration.
- Drill-down views for a line, stop, or vehicle.

### 3. Network map

A supplementary map will show buses, stops, and their latest available observations. The map is central to the passenger experience and provides additional context for operators.

## Data sources and hardware responsibilities

### Bus stop counts

A separate team member is responsible for on-device processing using an **Arduino UNO Q with 4 GB RAM**.

The hardware's focus is counting people present at bus stops. This repository is responsible for backend processing, the two web interfaces, and the simulator. The first version will simulate the hardware output.

### Vehicle counts

The prototype will simulate the number of people currently onboard each bus. Potential availability of GTT vehicle occupancy data has been mentioned but **has not been verified** and is not a dependency for the demo.

### What the counts do and do not represent

The available measurements are snapshots:

- People currently present at a stop.
- People currently present onboard a vehicle.

Boarding and alighting counts are not available. The system does not identify individual passengers.

Repeated snapshots must not be summed and presented as total passenger throughput or unique passengers: the same person can appear in multiple observations.

### Real transport geography

A candidate static GTT dataset is available at:

- [GTT GTFS archive](https://www.gtt.to.it/open_data/gtt_gtfs.zip)
- [Muoversi a Torino open data information](https://ls.muoversiatorino.it/it/open-data/)

Dataset contents, coverage, freshness, and applicable reuse terms must be checked before importing or redistributing data. Route selection and dataset validation are still pending. A static route and schedule dataset does not establish the availability of live passenger counts.

## Backend responsibilities and calculations

The prototype uses transparent calculations and rules. A machine learning model is not required for the agreed scope.

### Vehicle occupancy

For each vehicle:

- **Occupancy percentage** = onboard people / total capacity × 100
- **Remaining capacity** = max(total capacity − onboard people, 0)
- **People exceeding the seated capacity** = max(onboard people − seated capacity, 0)

Total capacity must be positive before computing a percentage.

The last measure is a comparison with the number of seats, not a direct measurement of standing passengers. The total onboard count cannot reveal exactly how many seats are occupied or free.

### Stop capacity concern

For the next relevant bus approaching a stop:

**Estimated excess demand = max(waiting people − remaining bus capacity, 0)**

Example: if 25 people are waiting and a bus has space for 10, the estimated excess demand is 15 people.

This is a simplified capacity indicator, not a guaranteed count of passengers who will be unable to board:

- Passengers may leave the bus before or at the stop.
- Other passengers may board at upstream stops.
- At stops served by multiple lines, the total waiting count does not reveal each person's intended line.
- Current counts do not predict the situation when the bus arrives.

The demo must label these assumptions. A shared stop's entire crowd must not be silently treated as confirmed demand for every line.

Alert persistence, severity thresholds, and the exact rule for selecting the next relevant bus still need to be defined.

### Journey context

The backend will associate the simulated origin, initial stop, selected destination, route direction, relevant stop sequence, and vehicle observations.

It will validate whether the destination is reachable under the prototype's same-line, no-transfer constraint.

### Historical aggregation

The backend will aggregate timestamped observations into the operator's statistics and charts. Aggregation intervals and weighting rules remain to be specified.

### Observation quality

Processing must distinguish between a valid zero count and an unavailable observation. The system must also handle stale readings, invalid values, and duplicate submissions, while preserving whether data is simulated or hardware-derived.

Unknown or stale counts must not silently produce reassuring zero-crowding values. Numeric freshness limits and validation rules will be defined with the ingestion interface.

## Planned architecture

```text
                       +---------------------------+
                       | Scenario controls         |
                       +-------------+-------------+
                                     |
                                     v
+----------------------+   +------------------------+
| Arduino stop counts  |   | Simulator              |
| (later integration)  |   | Stops, buses, positions |
+----------+-----------+   | and synthetic history  |
           |               +-----------+------------+
           |                           |
           +-------------+-------------+
                         v
              +-----------------------+
              | FastAPI backend       |
              | Ingestion, validation |
              | and persistence       |
              +-----------+-----------+
                          |
              +-----------v-----------+
              | Occupancy calculations|
              | Alerts and statistics |
              | Journey context       |
              +-----------+-----------+
                          |
              +-----------+-----------+
              |                       |
              v                       v
    +-------------------+   +----------------------+
    | Passenger web app |   | Operator dashboard   |
    | React/TypeScript  |   | React/TypeScript     |
    +-------------------+   +----------------------+
```

The simulator and future hardware adapter should feed the same processing flow, so replacing simulated stop observations does not require rewriting dashboard logic.

The design should support additional lines, stops, vehicles, and data sources through configuration and data models rather than hardcoded assumptions about two lines.

The database, API schemas, update transport, map library, and detailed repository layout have not been selected yet. No API endpoints are currently implemented or promised by this document.

## Simulation

The simulator will provide:

- Normal-service, rush-hour, and overcrowding scenarios.
- Controls to trigger a visible capacity concern during the presentation.
- Plausible changes in counts over time and along routes, rather than unrelated random values at every update.
- Simulated bus movement on the imported route geometry.
- Seven days of synthetic history for charts to be useful immediately.
- Reproducible data generation so scenarios and tests can be repeated.

Distributions, scenario parameters, vehicle capacities, and fleet sizes are still to be chosen. Synthetic data and movements must remain clearly identified in both interfaces.

## Validation approach

Field validation is outside the hackathon time budget.

Public datasets and research papers will be used where suitable to justify assumptions, build scenarios, or provide comparison points. No passenger-count benchmark or paper has been selected yet, and no measured accuracy claim is currently supported.

Planned software checks include:

- Occupancy and remaining-capacity calculations at empty, seated-capacity, and total-capacity boundaries.
- Invalid or missing capacity and passenger-count inputs.
- Alert creation, updates, acknowledgement, and resolution.
- Missing, stale, duplicate, and out-of-order observations.
- Same-line journey selection, route direction, and unreachable destinations.
- Consistency between synthetic history, live observations, charts, and alerts.
- End-to-end demonstration of normal service, overcrowding, and recovery.

Software tests and synthetic benchmarks cannot establish the accuracy of the physical counting hardware.

## Development roadmap

- [x] Agree on the prototype's users, scope, and technology.
- [x] Create the GitHub repository and document the initial project decisions.
- [ ] Verify the GTT dataset and select two complete bus lines.
- [ ] Define data models, ingestion contracts, storage, and update delivery.
- [ ] Implement the simulator and seven-day synthetic history.
- [ ] Implement backend calculations, alerts, and historical queries.
- [ ] Build the passenger web app.
- [ ] Build the operator dashboard.
- [ ] Add suitable public-data or research-based comparison scenarios.
- [ ] Test and rehearse the local demo.
- [ ] Integrate Arduino observations after the initial software prototype.

Later extensions may include a larger urban network, verified external vehicle data, real hardware ingestion, remotely accessible deployment, crowding forecasts, and route optimization.

## Running the project

There is no runnable application yet. Installation requirements, environment variables, and verified startup commands will be added as the backend and frontend are implemented.

The initial target is localhost on the presentation computer. The passenger interface can be demonstrated using a mobile-sized browser viewport. Sharing the app with other devices or publishing it online is deferred.

## Documentation and version control

This README is the current project overview and decision record. Update it whenever an agreed requirement, implementation milestone, or limitation changes.

Keep implemented capabilities clearly separated from planned work. Add setup instructions only after verifying them, and record assumptions behind metrics and simulations. Publish documentation and code changes through descriptive Git commits.

### Decision record

| Date | Decision |
| --- | --- |
| 2026-10-10 | Build separate passenger and operator interfaces backed by a shared backend. |
| 2026-10-10 | Use Python/FastAPI and React/TypeScript. |
| 2026-10-10 | Measure snapshots of people present; boarding and alighting counts are unavailable. |
| 2026-10-10 | Focus hardware work on stop counts and simulate vehicle occupancy. |
| 2026-10-10 | Use two complete real GTT lines independently, with no transfers in the first version. |
| 2026-10-10 | Use a simulated passenger origin and a passenger-selected destination stop. |
| 2026-10-10 | Show crowding along the selected route; defer route optimization and forecasting. |
| 2026-10-10 | Prioritize demand-versus-capacity alerts and operator acknowledgement. |
| 2026-10-10 | Include controllable simulation scenarios and seven days of synthetic history. |
| 2026-10-10 | Run the initial demo entirely on localhost. |
| 2026-10-10 | Use public data or research for software scenarios; defer field validation. |

## Open decisions

- Which two GTT lines to import and which route variants to support.
- How to handle nearest-stop selection when the destination is on the other independent line.
- How to represent demand at stops shared by multiple lines.
- Vehicle fleet size, capacities, schedules, and simulation parameters.
- Database, API contracts, refresh cadence, and map implementation.
- Alert persistence, severity, stale-data thresholds, and aggregation rules.
- Specific public datasets or papers for comparison and their licensing requirements.
