# Frontend v2

React/TypeScript, Vite and Leaflet. All runtime activity is explicitly synthetic. No production backend logic is changed by this branch.

## Run and verify

```powershell
cd frontend
npm ci
npm run dev
npm test
npm run build
```

Use Node 22.18+ or 24. Vite prints the actual localhost port. `/#citizens` and `/#operators` share simulation state in one tab; separate tabs are independent. History is hidden from the citizen interface but not protected by authentication.

## Implementation

- `simulation.ts`: seeded private queue/destination and vehicle state; capacity-constrained boarding, alighting, one shared queue per stop; 60-second periodic observations, pre-arrival and post-departure observations. Simulation time advances in ten-second internal steps.
- `predictions.ts`: consumes only public observations and learned aggregates, never private passenger destinations. Stop predictions anchor historical levels to current counts and estimate approaching bus effects. Bus predictions use learned net occupancy changes and observed demand.
- `model.ts` / `model.worker.ts`: seven days of training, a separate calibration week and independent test week with disjoint seeds. Browser worker keeps preparation off the UI thread. Models are cached in memory per scenario.
- `data.ts`: adapter and snapshot assembly, ready to be replaced by an agreed server adapter.
- `MapView.tsx`: stable markers and route layers preserve map zoom, focus and tooltips during updates. Every physical stop ID renders once, even across routes.

## Synthetic assumptions

Four lines, five vehicles, 271 unique imported stops. Full reverse patterns are visible but have no simulated buses. Travel is three minutes per segment, dwell is 30 or 60 seconds based on simulated boarding/alighting; terminal recycling waits ten minutes and starts a new synthetic trip. Marker travel interpolates between stop coordinates, not GPS or traffic measurements.

Each queue contains line-specific groups and flexible groups with a common downstream destination on 33/42. Destinations remain private to simulation. Some people leave queues independently of buses; this is not surfaced as measured abandonment. Demand varies by time and scenario. There are deterministic four-minute sensor outage windows to exercise freshness.

Historic stop profiles are keyed by stop, weekday/weekend and 15-minute bucket. Net occupancy-change averages are keyed by route pattern and stop. A fresh count residual decays with a 15-minute time constant. Stop forecasts deduct estimated boardings on buses expected to depart within the horizon. Bus forecasts combine historical positive net change and observed demand (60/40 weighting). Coefficients are fixed demo assumptions, not optimized using the final test week.

Bus reliability at an arbitrary arrival ETA is unavailable unless it exactly matches a calibrated fixed horizon. Fixed +5/+10/+15-minute bus forecasts are available in the expandable card. Reliability is empirical category accuracy, not a guarantee for an individual prediction. At least 30 calibration samples are required; category-specific test results expose imbalance and calibration drift.

Training history retains hourly means and one-minute aggregates: very busy stop-minutes, stale/missing stop-minutes and possible capacity-pressure stop-minutes. Bus history is sampled hourly. Pressure compares a single observed queue with combined space on buses approaching within ten minutes; intended lines remain unknown, so this is only a heuristic concern. It is not throughput or unique passengers.

The demonstration clock and profile weekday handling use UTC+2 for the September/October 2026 simulation dates, not a general daylight-saving calendar. Production timestamps and timezone handling must be supplied by the server.

## Geography and limitations

Static GTFS 20261009, one common full pattern per direction of 18, 68, 33, 42. `tools/import_gtfs.py` regenerates the fixture. No live operator measurements are included. Public source attribution stays in technical documentation; the operator is not affiliated with the project.

Capacities and thresholds are illustrative. Free seats cannot be inferred. Forecast map changes stop counts only; bus markers retain current simulated positions. No transfers, walking directions, prediction of individual intentions, server persistence or field validation.

See the root README and `docs/API_CONTRACT.md` for integration status.
