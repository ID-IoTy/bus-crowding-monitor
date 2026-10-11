# AGENTS.md - Rules for AI agents and contributors

## Project in five lines

Bus Crowding Monitor predicts crowding on buses and at stops for GTT lines 33 and 42 in Turin.

- One FastAPI backend (:8000) contains a simulated world (`app/sim`: clock, passengers, buses with APC, stop cameras) and a core (`app/core`) that ingests those sensor events as if they were real, predicts crowding with calibrated confidence and raises alerts.
- A React/TypeScript frontend (:5173) shows the operator dashboard, which is the focus of the demo.
- An Arduino UNO Q (:8080) can replace one simulated camera with a real one.

Read before working:

1. This file.
2. [`docs/SPEC.md`](docs/SPEC.md): the sections your task links to. The SPEC is the source of truth.
3. Your task file in [`docs/tasks/`](docs/tasks/README.md).

## Stack

| Area | Choice |
| --- | --- |
| Backend | Python 3.12, uv, FastAPI, Uvicorn, SQLAlchemy 2, Pydantic v2, httpx, numpy, scikit-learn (P1), PyYAML, tzdata, pytest, ruff |
| Frontend | Node 20 LTS, npm, Vite, React, TypeScript, react-leaflet + OpenStreetMap, Recharts, TanStack Query, Vitest + Testing Library |
| Types | `openapi-typescript` from the backend OpenAPI schema |
| OS | Windows + PowerShell |

Do not add other libraries without a reason written in the SPEC decision record. Pin exact versions and commit the lock files (`uv.lock`, `package-lock.json`).

## Commands

| Task | Command |
| --- | --- |
| Backend tests | `cd backend; uv run pytest` |
| One test area | `cd backend; uv run pytest tests/sim -k clock` |
| Lint | `cd backend; uv run ruff check .` |
| Bootstrap data | `cd backend; uv run python -m app.cli bootstrap --weeks 1` |
| Run backend | `cd backend; uv run uvicorn app.main:app --host 127.0.0.1 --port 8000` |
| Frontend tests | `cd frontend; npm test` |
| Run frontend | `cd frontend; npm run dev` |
| Generate TS types | `./scripts/gen-types.ps1` |
| Run everything | `./scripts/dev.ps1` |
| Arduino mock | `cd backend; uv run python ../edge/mock_edge.py --port 8080` |

Never start long-running servers (`uvicorn`, `npm run dev`, `dev.ps1`) in a blocking way from an agent shell. Use FastAPI's `TestClient`, `httpx.ASGITransport` or Vitest for verification, and ask the user to run servers manually.

## Hard rules

1. **Contracts first.** Every message and view is a Pydantic model in `backend/app/contracts`. Add or change the contract before the code that uses it. A contract change must update SPEC section 6 and regenerate `frontend/src/api/generated.ts` in the same change. Mention it in your summary.
2. **Isolation.** `app/core` never imports `app/sim` and never reads `sim.sqlite`. Sim and core talk only through `IngestPort` and `CameraPort` (`app/contracts/ports.py`). Wiring happens only in `app/main.py` and `app/cli.py`. The test `tests/test_isolation.py` enforces this.
3. **Simulated time everywhere.** Every timestamp is simulated time from `SimClock`, ISO 8601 with the Europe/Rome offset. Never call `datetime.now()` in `app/sim` or `app/core`. The only real-time values are the scheduler pacing, the Arduino timeout and `device_measured_at`.
4. **Provenance.** Every value exposed to the frontend carries `kind` (`observed`, `predicted`, `simulated`) and its timestamp. Observed values also carry `source`.
5. **Stale is not zero.** Missing or stale data (older than 180 s simulated) is `null` with a status, never 0. In the UI it is shown as unavailable.
6. **Determinism.** Every random draw goes through a seeded `numpy.random.Generator`. Tests use a fixed seed and must be reproducible.
7. **Constants in config.** Numeric parameters live in `data/config/sim.yaml`, `data/config/model.yaml` or `data/scenarios/*.yaml`, with the values from the SPEC. No magic numbers in code.
8. **Stay in your system.** Edit only the folders of the system your task belongs to (see the task file). If you need a change elsewhere, stop and describe it instead of making it.
9. **Label simulated data.** Nothing simulated may look real. The UI shows a permanent "simulated data" banner. Mock data is labelled as mock.
10. **Security honesty.** The backend has no authentication and binds to `127.0.0.1`. Never bind to `0.0.0.0` and never remove that note. If you add a network-facing endpoint, say so explicitly in your summary.
11. **Out of scope.** Do not implement items listed as non-goals in SPEC section 1 (Telegram, voice, GTFS-RT, improved ETA, fare evasion, LoRa, auth).
12. **Ambiguity.** If the SPEC does not answer a question, choose the simplest option consistent with it, add a row to the SPEC decision record (section 16) and mention it in your summary. If the choice changes a contract or the scope, ask first.

## Conventions

- **Python:**
  - type hints everywhere, ruff for lint and format, `snake_case` modules;
  - one module per responsibility: `app/sim/clock.py`, `app/core/correlation.py` and so on;
  - tests in `backend/tests/<package>/test_<module>.py`, integration tests in `backend/tests/integration/`.
- **API:**
  - routes in `app/api/`, thin, no business logic;
  - errors: `422` for invalid payloads, `404` for unknown IDs, `409` for invalid state transitions.
- **TypeScript:**
  - strict mode, function components, data access only through `src/api`, never `fetch` in components;
  - generated types are not edited by hand;
  - tests next to the component (`*.test.tsx`).
- **Accessibility:** levels use colour and text, controls are keyboard accessible and labelled.
- **Git:**
  - frontend work stays on the `frontend` branch until it is aligned;
  - other work goes on short branches named `feat/<task-id>-<slug>` (for example `feat/K3-prediction`), merged into `main`;
  - only commit when asked; never force-push.

## Task workflow

1. Open your task in `docs/tasks/<system>.md`. Check that every dependency is marked `done`.
2. Read the linked SPEC sections.
3. Implement the task, with the tests it lists.
4. Run the acceptance command and check the expected output.
5. Mark the task `Status: done` in the task file, and write two lines of notes under it if something differs from the plan.

## Definition of Done (every task)

- [ ] The acceptance command of the task passes, with the expected output.
- [ ] `uv run pytest` (backend) or `npm test` (frontend) is fully green, not only the new tests.
- [ ] `uv run ruff check .` is clean (backend).
- [ ] No contract changed silently: if one changed, SPEC section 6 and the generated TS types are updated.
- [ ] Constants are in config files, not in code.
- [ ] No orphan code, TODO without a task ID, or debug prints.
- [ ] Decision record updated if a decision changed.
- [ ] Task status updated in its task file.
