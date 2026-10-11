# BusFlow frontend

The integrated entry point is `src/LiveApp.tsx`, imported from `src/main.tsx`. Both passenger and operator views use the shared HTTP/WebSocket adapter in `src/api/client.ts`. Leaflet styles are imported globally so both maps render correctly.

## Run

Start the active FastAPI backend on `127.0.0.1:8000` first (see the root README). Then, from this directory:

```powershell
npm ci
npm run dev -- --port 5174
```

Passenger app: `http://127.0.0.1:5174/#citizens`. Control room: `http://127.0.0.1:5174/#operators`. `VITE_API_URL` overrides the default API address. A disconnected backend produces an explicit error; there is no silent fallback to the previous frontend simulator.

The passenger view searches online addresses/places, automatically proposes compatible nearby stop pairs, and displays up to three backend services per route/direction. Destination and departure time are optional. The map shows route-average or selected-service forecasts; unknown values remain neutral. Desktop uses panels left/map right; smaller screens stack the workspace.

Service and historical data are synthetic. The demo assumes 70 total places, with unknown seated capacity and unavailable validated reliability. The control room supports alerts, acknowledgement, simulator controls and the Mediterraneo camera-mode switch; advanced history is deferred to P1.

## Checks

`npm test` runs 19 domain, journey and place-search tests, including preserved standalone-model tests. `npm run build` runs TypeScript checks and the production build. These do not replace full integrated browser or real-hardware acceptance. Generate API types from the repository root with `./scripts/gen-types.ps1`.

Old standalone modules remain for tests and reference. Earlier delivered versions are preserved on their original GitHub branches; see `docs/VERSIONING.md` in the repository root.

The control room now includes the backend-connected History & insights tab and shares the passenger workspace palette, rounded panels and responsive touch controls. Historical observation charts offer period, line/direction and stop filters; generated types include HistoryView. Calibrated forecast accuracy is still unavailable.
