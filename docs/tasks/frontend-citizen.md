# Frontend: citizen app (P2)

A smartphone-first view of the same predictions for passengers. It is not part of the demo. Start only when the operator P0 tasks are done.

- **May edit:** `frontend/src/citizen/` only.
- **Reuse:**
  - the adapter, hooks and shared components from `frontend/src/api` and the operator shared components;
  - if you need a change there, describe it to the operator workstream.
- **SPEC:**
  - [section 6](../SPEC.md#6-message-contracts-who-sends-what-to-whom) (`/api/journey`, `/api/stops`);
  - [section 9](../SPEC.md#9-models-and-prediction-engine) levels;
  - [section 12](../SPEC.md#12-frontend) citizen app and rules.

The UI rules of [`frontend-operator.md`](frontend-operator.md#ui-rules) apply: kind and age on every value, "unavailable" instead of 0, colour plus text, the simulated data banner, and keyboard and screen-reader access. Layouts are mobile first (360 px wide).

---

## Z1 - Citizen map and origin

- **Priority:** P2
- **Status:** todo
- **Depends on:** O1, K3

### Objective

A mobile map where the passenger picks an origin and gets the nearest stop.

### Instructions

- Map with live buses and stops (reuse the O2 layers in a simplified style).
- The origin is either a simulated position (default: a point near a shared stop) or a point chosen on the map.
- The nearest stop is preselected as the starting stop.

### Tests

The nearest stop is computed correctly on fixture coordinates.

### Acceptance

```powershell
cd frontend
npm test   # green
```

### Demo

`?app=citizen` opens the map with the starting stop selected.

---

## Z2 - Journey view

- **Priority:** P2
- **Status:** todo
- **Depends on:** Z1, K8

### Objective

Show the passenger how crowded each segment of their journey will be.

### Instructions

- The destination is chosen among the downstream stops of the same line and direction.
- `GET /api/journey` returns the journey, shown as a vertical list of stops coloured by predicted onboard level, with confidence per segment and the next buses.
- A `422` with `wrong_direction` or `needs_transfer` is explained in plain words, and not shown as a valid journey.

### Tests

- A valid journey renders the SPEC example item (78, orange, 61%).
- Both `422` reasons show their explanation.

### Acceptance

```powershell
cd frontend
npm test   # green
```

### Demo

A journey coloured segment by segment, with confidence.

---

## Z3 - Citizen stop detail

- **Priority:** P2
- **Status:** todo
- **Depends on:** Z1, K3

### Objective

What the passenger sees when they zoom on a stop.

### Instructions

Tapping a stop shows:

- observed and predicted waiting;
- the next buses with ETA;
- the predicted onboard crowding at departure;
- `may_not_fit` as a clear text warning.

### Tests

- Renders the SPEC `GET /api/stops/{stop_id}` example.
- A stale value shows "unavailable".

### Acceptance

```powershell
cd frontend
npm test   # green
```

### Demo

The same information as the physical stop display, on the phone.
