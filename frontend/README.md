# Frontend prototype

Independent React/TypeScript passenger app and operator dashboard. The transport operator is not a project partner. All runtime transit activity is currently mocked; the backend is being implemented independently.

## Run locally

Prerequisite: Node.js 22.18+ (or Node.js 24) and npm. Development was verified with Node.js 24.14.

From the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open:

- Passenger view: http://127.0.0.1:5173/#citizens
- Operator view: http://127.0.0.1:5173/#operators

Both interfaces share one application and simulation state in a browser tab. Separate tabs initialize their own demo state; this is not a shared multi-user server simulation.

## Checks

```powershell
npm test
npm run build
```

Tests cover capacity boundaries, forward-only journeys, nearest-stop distance, the exact demo fleet, and scenario recovery.

## Demo fleet

| Vehicle | Public route pattern | Direction |
| --- | --- | --- |
| BUS-1801 | 18U-0 | Piazza Sofia |
| BUS-1802 | 18U-0 | Piazza Sofia |
| BUS-6801 | 68U-0 | Via Cafasso |

The two line 18 buses start at different positions in the same direction and have different illustrative arrival times. Return-direction patterns are visible, but have no simulated service.

Counts, movement, ETA, predicted occupancy, capacities, and historical series are synthetic. Assumed vehicle capacity is 75 people including 32 seats; these are not verified vehicle specifications.

Scenario controls provide normal service, rush hour, and overcrowding. Pause freezes movement; Reset returns to the initial normal scenario. Mock snapshots update every five seconds, with time accelerated for presentation. Vehicles loop after reaching the end of their pattern.

Operator acknowledgement is local to the current browser session. Scenario recovery clears active alerts. Production acknowledgement and resolution must come from the backend.

## Geography

`public/network.json` is an extracted GTT fixture:

- Source: https://www.gtt.to.it/open_data/gtt_gtfs.zip
- Feed version: 20261009
- Service dates declared by the feed: 2026-10-08 through 2027-01-31
- One common full trip pattern per direction of lines 18 and 68.
- Stop counts: 18U-0: 50, 18U-1: 50, 68U-0: 41, 68U-1: 40.
- Other trip patterns and route variants are omitted.
- No GTT live positions, APC measurements, or occupancy forecasts were imported.

The import uses `routes.txt`, `stops.txt`, `trips.txt`, `stop_times.txt`, and `shapes.txt`. Stop times provide ordering; the demo does not use GTT schedules for ETAs.

To regenerate after downloading the archive into the repository root:

```powershell
python tools/import_gtfs.py gtt_gtfs.zip frontend/public/network.json
```

The archive itself is ignored by version control. Confirm dataset reuse terms before public redistribution. The repository is currently private.

Leaflet renders the map with attributed OpenStreetMap tiles. The basemap and optional Google Fonts need an internet connection; route geometry is bundled locally. If tiles fail, the UI reports it and retains route overlays and markers. Localhost does not mean all visual assets are offline.

## Backend integration

Data access is centralized in `src/data.ts`. `getSnapshot()` currently creates deterministic mock observations and illustrative predictions.

Replace that adapter with the colleague's API client once response shapes are agreed. Preserve the distinction between observed readings, server predictions, and mock values. Do not move production prediction or alert logic into React components.

The types in `src/types.ts` are frontend view models, not a finalized server API. The UI currently needs:

- Lines, direction patterns, ordered stops, and geometry.
- Vehicle identity, route/direction association, position, occupancy, and capacity.
- Waiting counts and observation timestamps.
- Per-bus predictions for a stop: occupancy, ETA, provenance, and prediction time.
- Alerts, acknowledgement state, and historical aggregates.

A live adapter also needs loading/error states, freshness, missing values, polling or push updates, and server-backed alert actions. Unknown counts must not become zero.

## Current limitations

- No transfers or route optimization.
- Simulated starting positions are placed at preset stops.
- Forecasts are fixtures rather than validated statistical estimates.
- Synthetic charts show a typical day and seven daily summary points, not stored raw observations.
- The history chart is network-wide; the network filter applies to current metrics and the route table.
- Acknowledgement, scenario selection, and simulation are not shared across tabs.
- No physical display frontend is implemented.
