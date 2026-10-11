# Integrated P0 API

The active server is `backend/app/main.py`, on `http://127.0.0.1:8000`. Generated schemas are `frontend/openapi.json` and `frontend/src/api/generated.ts`; interactive documentation is `/docs`. The integrated browser uses `frontend/src/api/client.ts`.

## Read endpoints

- `GET /api/health`: status, simulated timestamp and historical-model availability.
- `GET /api/lines`: route patterns, ordered stops, geometry and reference offsets; only lines 33/42.
- `GET /api/lines/{line_id}`: one route pattern, using its pattern ID, not just the public line number.
- `GET /api/stops`, `/api/stops/{stop_id}`: deduplicated stop readings; the detail includes upcoming forecasts.
- `GET /api/vehicles`, `/api/vehicles/{vehicle_id}`: latest vehicle observations.
- `GET /api/journey?from=3380&to=<optional-stop-id>&requested_at=<optional-ISO-timestamp>`: compatible direct route/direction options with up to three services. Omit `to` or use an empty value for no destination; omit `requested_at` for simulated Now.
- `GET /api/operator/alerts`: alert evidence and lifecycle state.

Stop IDs use raw GTFS strings (for example `3380`), without a prefix. Times use timezone-aware ISO 8601 strings. Journey services separate current observations, arriving load, after-departure load, capacity, percentage and position provenance. Reliability remains null. A preceding destination or identical endpoints is not a valid direct journey.

## Mutations

- `POST /ingest/vehicle/approach`, `/ingest/vehicle/departure`, `/ingest/camera/observation`: typed sensor messages, deduplicated by message ID. Consult the generated schema for field names.
- `POST /api/operator/alerts/{id}/ack`: acknowledge an open alert; resolved alerts cannot be acknowledged.
- `POST /sim/clock`: optional `paused` and `speed` (1–60).
- `POST /sim/scenario`: `name` in `normal`, `rush_hour`, `overcrowding`.
- `POST /sim/cameras/{camera_id}/mode`: `mode` in `simulated`, `physical`; physical mode is supported for `cam-3380`.
- `GET /sim/state`, `/sim/scenarios`, `/sim/cameras`: current simulator state and configuration.
- `GET /sim/truth`: debug-only simulated truth; not a prediction input.

Check `/docs` for the exact ingestion paths and current model schema. The generated schema takes precedence over examples in earlier planning documents.

## Live updates and camera

`WS /ws/live` sends typed envelopes with live clock, vehicles, stops and alerts. The client refreshes its API data from these notifications and also polls. It does not fall back to old synthetic frontend counts.

The device serves `GET /count` with `count` and a device `measured_at`, and accepts typed `POST /display` payloads. The backend assigns simulated observation time separately from device measurement time. Camera failure leaves stale readings unavailable. See `edge/README.md` for the controllable mock.

This is a local unauthenticated demo. Browser origins are restricted to localhost/127.0.0.1 ports 5173 and 5174; the PC server stays on loopback. Physical device endpoints are restricted operationally to the private demo LAN.


## Operator historical observations

`GET /api/operator/history` supports optional ISO date `start`/`end`, `route_id` (directional pattern ID) and `stop_id`. The default range is the available synthetic archive, not the current simulation date. At most 31 inclusive days can be selected. Unknown IDs return 404 and invalid ranges return 422.

The `HistoryView` response contains source `synthetic_history`, available/selected dates, sample counts, weighted sample means, hourly/daily series and the ten busiest stops. Missing buckets are null, never fabricated zero. Waiting uses periodic camera readings only, deduplicated by physical stop; route filters include waiting at that route's stops, without claiming all waiting passengers use that route. Bus occupancy uses that direction's after-departure APC readings, divided by the assumed 70-place capacity. High-load percentage is the share of departure samples above 90%, not time spent full. No prediction accuracy is inferred.

The archive is immutable during a server session. Initial aggregation is cached in process; bootstrap must run offline and the backend must restart after rebuilding history. No simulator truth is read for these charts. The operator endpoint is local and unauthenticated like the rest of the demo; the UI exposes it only in the control room, which is not an access-control boundary.
