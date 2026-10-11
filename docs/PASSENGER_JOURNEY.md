# Passenger journey model and backend handoff

This is a frontend-only, deterministic service simulator. No measurements, operator timetable, calibrated ML or production backend are implied. The previous five-bus operator simulation is retained independently; only clock and scenario controls are shared.

## Search and output

Inputs: physical `origin` stop ID; optional `destination` stop ID; earliest arrival time at the origin, represented as an ISO timestamp; current simulated timestamp; scenario. UI date/time is Europe/Rome (DST aware). A nonexistent spring DST time is rejected; the earlier occurrence is used for an ambiguous autumn time. Past queries are rejected, and Now clears the date/time input.

A compatible pattern must contain the origin before its terminus and, when supplied, the destination later in the same ordered stop list. Opposite platforms are distinct stop IDs. Same-stop journeys and transfers are unsupported. No match returns an empty list, not unrelated services. Removing destination restores all departing patterns.

`journeyOptions` returns route groups with three ordered `JourneyTrip` objects, plus origin/destination indices. Each trip contains a stable ID (pattern + initial arrival timestamp), capacity (nullable), positions with `simulated-current`, `predicted` or `not-started` provenance, latest departure observation (nullable), and an ordered passage list. A passage separates arrival/departure timestamps, arriving people, estimated alighting, boarding, leaving people, excess demand and nullable occupancy percentage. Reliability is always null until this target has independent calibration. This is an in-process frontend contract, not an implemented HTTP endpoint.

The UI's main number is leaving people / total capacity, labelled **After your stop**. An unknown capacity never becomes zero percent or a verified claim of spare capacity. Free seats cannot be inferred. The observation shown is the most recent completed departure of this synthetic trip; tomorrow's trips do not receive invented current observations.

## Schedule and demand assumptions

- Eight imported line/direction patterns, including return directions. Each has a service every ten minutes around the clock. The phase is a deterministic pattern-ID hash modulo ten minutes. This artificial 24-hour timetable supports any requested date and midnight rollover; it is not a real service calendar.
- Three minutes travel plus 30 seconds dwell per stop. Times do not change with traffic or boarding; a future backend may replace them. A trip starts empty at its first stop and empties at its last stop. No physical fleet assignment, driver roster, depot availability or vehicle turnback model is claimed.
- All demo capacities are 70 total passengers. Capacity is nullable in the trip model; no seat inventory is used.
- Historical waiting profile: base `3 + hash(stopId) % 7`, plus morning/evening Gaussian peaks of amplitude five at 08:00 and 18:00 (widths 1.6 and 1.8 hours). Weekend multiplier 0.8. Scenario multipliers: normal 1, rush 1.5, overcrowded 2.2. These are authored assumptions, not fitted historical measurements.
- A synthetic observation is available each minute; a deterministic variation between -3 and +3 changes every five minutes. Counts never go below zero. Forecast waiting adds the recent observation-minus-profile residual to the future profile with a 15-minute exponential decay.
- Expected demand is split equally among patterns serving the physical stop with onward service. Intended passenger lines remain unknown. This is a demand approximation, not a conserved multi-line queue: waiting counts do not simulate persistent left-behind people or abandonment.
- At each passage, alighting is 12–21% of the arriving count (deterministic stop-specific fraction), rounded and bounded. Terminal alighting is everyone. Boarding is bounded by the remaining total capacity. `leaving = arriving - alighting + boarding`. Estimated excess waiting triggers a possible inability-to-board warning, not a guarantee about any individual.
- Completed passages use deterministic observations at passage time; their counts do not change on later refreshes. Future passages use forecast waiting. The path recursively propagates leaving counts into the next arrival, so both current simulated bus history and future demand affect the result.

## Map interpretation

Stop positions are projected monotonically onto the imported polyline. Marker positions interpolate along that shape with a dwell pause; they are not real GPS. Trips not yet started stay at the origin terminus with a scheduled label. Nearby marker labels are visually offset for selection without changing coordinates.

For each stop-to-stop segment, use the after-departure forecast at its upstream stop. Smoothly interpolate towards the next forecast along short pieces of the actual shape. The aggregate view averages only the available forecasts from the displayed trips. Departures in the past relative to the current simulation time contribute no forecast. No contributors or unknown capacity means grey. The gradient is a visual interpolation, not continuous sensor coverage: green at 0%, yellow at 40%, orange at 65%, red at 100%.

Destination filtering emphasizes only the requested segment but retains the full route at lower opacity. Stop dots appear from zoom 15, with A/B endpoints always visible. Dot colour uses a 30-person illustrative reference, not a physical capacity or safety threshold.

## Verification and integration boundary

Automated tests cover optional destination, direction/order, all eight patterns, three distinct arrivals, future dates/midnight, invalid/past times, DST, capacity unknown, flow conservation, saturation, terminal emptying, stable completed observations and monotonic shape projection. UI checks cover searching, map/card selection, zoom visibility, optional destination and date/time controls.

No backend, Arduino or main/integration branch is modified. Before production, replace synthetic schedule, observations and historical profiles through the agreed backend adapter and validate the after-departure target independently. Legacy operator evaluation metrics do not measure this model.
