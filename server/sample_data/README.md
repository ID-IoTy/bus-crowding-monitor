# Sample Data — One Week of API Payloads

This folder contains a week of **example API payloads** that reproduce the
requests the central server received during the previous week, split by source:

| File | Mirrors | Contents |
|---|---|---|
| `bus_events_week.jsonl` | `POST /ingest/bus-event` | APC payloads sent by buses on each stop departure |
| `stop_events_week.jsonl` | `POST /ingest/stop-event` | camera/sensor payloads from the stops |

Each line is one JSON object — exactly the HTTP body an Arduino device would
have POSTed. The files are time-ordered, so they read like a real event log.

## The week

- **Start:** Monday 2024-01-08, 06:00 → Sunday 2024-01-14
- **Mon–Fri:** full demand with morning (08:00) and evening (18:00) rush peaks
- **Sat:** ~60% demand, **Sun:** ~45% demand (flatter peaks)
- **Network:** 2 routes × 40 stops, 3 buses (capacity 75), 8 trips/bus/day
- **Anomalies:** a handful of near-full buses and abandonment-style crowd drops
  are injected so the dataset contains interesting edge cases

Volumes: ~6,700 bus payloads and ~20,000 stop payloads (periodic + pre_arrival +
post_departure).

## How the data feeds the model

The two streams are internally consistent: the bus onboard counts and the
stop before/after crowd counts line up. When replayed through the server, the
**correlator** reconstructs how many people boarded and alighted at each stop
and the dwell time — these `correlated_events` are what `ml/train.py` trains on.

```
JSONL payloads ──► correlator ──► correlated_events ──► ml/train.py ──► model.joblib
```

The ML model does **not** learn from the raw payloads directly; it learns from
the correlated boarding figures, exactly as it would from live production
traffic.

## Reproduce / load

```bash
# (Re)generate these files
python -m simulator.generate_sample_week --start 2024-01-08

# Load them into the DB (seed first so routes/stops/buses exist), then train
python seeder.py
python -m simulator.load_sample_data
python -m ml.train
```

### Example payloads

Bus event (`bus_events_week.jsonl`):
```json
{"bus_id": "BUS-01", "route_id": "R1", "stop_id": "R1-S01", "timestamp": "2024-01-08T06:02:38Z", "passengers_onboard": 8, "door_status": "closed", "speed_kmh": 0}
```

Stop events (`stop_events_week.jsonl`) — the pre/post pair around a departure:
```json
{"stop_id": "R1-S00", "timestamp": "2024-01-08T05:59:55Z", "people_waiting": 3, "event_type": "pre_arrival"}
{"stop_id": "R1-S00", "timestamp": "2024-01-08T06:00:10Z", "people_waiting": 0, "event_type": "post_departure"}
```
