# Frontend/backend integration contract

Status: v2 frontend view model proposal, compared against backend commit `0c87766a13e9b5c7edb2d19e66da74b2fda2113c`. This is not a claim that these fields already exist on the server.

## Existing endpoints

- POST `/ingest/stop-event`: stop_id, people_waiting, event_type, timestamp.
- POST `/ingest/bus-event`: bus_id, route_id, stop_id, passengers_onboard, door_status, timestamp and optional location.
- GET `/stops/{id}/status`: current_waiting and upcoming buses with ETA strings and occupancy percentages.
- GET `/buses/{id}/route-forecast`: current occupancy percentage and per-stop departure forecasts.
- GET `/admin/anomalies`: operator anomaly list, admin key required.
- GET `/health`: no authentication.

Arduino's existing ServerReporter posts the matching JSON and X-API-Key header. Its defaults refer to `R1-S05`, `BUS-01`, `R1`, not GTFS IDs. It currently reports periodic/stable counts without real arrival/door triggers.

## Required v2 concepts

- Physical stops: stable ID, name, coordinates, illustrative or verified waiting capacity, associated route patterns.
- Route patterns: line, direction, ordered physical stop IDs and geometry; stop IDs are not duplicated per line.
- Observations: entity ID, count (nullable if absent), measured_at, received_at, provenance. Never set measured_at to response retrieval time.
- Bus state: bus/trip/pattern IDs, onboard observation, total and seated capacity, current position and next stop.
- Stop forecasts: stop ID, generated_at, target_at, horizon_minutes (5/10/15), predicted count/category, live-history or history-only basis.
- Reliability: nullable percentage, calibration sample count, horizon/category, model version and validation scope. Synthetic scores must never be applied to the production backend model.
- Bus arrival forecasts: arrival ETA with full date/time, count and category before boarding; distinguish from departure forecasts.
- Operator history: filtered aggregates, measurement completeness, error metrics and calibration/test cohorts.

`frontend/src/types.ts` describes the demo view models. Endpoint names for the extended contract remain to be agreed; do not invent equivalence with the current server payloads.

## Concrete mismatches to address

1. Backend Stop has a single route_id/sequence; real GTFS physical stops can belong to multiple route patterns. This requires a topology migration, not mapping by array index.
2. Backend seed data is synthetic R1/R2 geometry and schedules. It is not the imported 18/68/33/42 network.
3. Current status returns 0 when no observation exists and omits its timestamp. The UI must not call that a fresh measured zero; add nullable count and observation time before showing freshness.
4. `seats_available_on_arrival` is calculated from total capacity, so it is not a free-seat measurement. Do not display it as seats.
5. Current ETA strings omit date/timezone; do not silently interpret them as absolute local timestamps across midnight.
6. No fixed-horizon stop forecasts or calibrated reliability endpoint exists yet. Show unavailable in a server-connected view instead of substituting demo predictions.
7. The backend correlation formula estimates flows under assumptions. Counts do not uniquely determine boarding/alighting or abandonment. The UI must label them as estimates.
8. Device retries lack stable event IDs; deduplication and bus_visit IDs are a later ingestion change.

## Integration acceptance

First verify the existing Arduino reporter payload can be accepted by FastAPI and that a browser can read the resulting count. Use the server's own synthetic IDs for this test. Keep the four-line demo separate until shared topology and forecast contracts are implemented. Test network errors and authentication without storing keys in committed files. Never send an admin key to citizen clients.
