# 🚌 SmartBus Central Server

> AI-powered real-time public transport intelligence for Smart Cities

![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green?style=flat-square&logo=fastapi)
![SQLite](https://img.shields.io/badge/Database-SQLite-lightblue?style=flat-square&logo=sqlite)
![scikit-learn](https://img.shields.io/badge/ML-scikit--learn-orange?style=flat-square&logo=scikit-learn)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

---

## Overview

A central backend server that ingests real-time data from buses (via APC units) and smart bus stops (via Arduino cameras/sensors), correlates events, predicts crowdedness and adjusted ETAs, detects anomalies, and exposes a REST API for citizen mobile apps and physical stop displays.

This project is built for the **HackTurin** hackathon, simulating the GTT public transport network in Turin, Italy.

**Key capabilities:**
- Real-time ingestion from Arduino-based hardware over local WiFi
- Event correlation: cross-references bus and stop data to compute boarding/alighting counts
- ML-powered crowdedness prediction (% occupancy on arrival AND after boarding) for all upcoming stops
- ETA adjustment that accounts for boarding time, compared side-by-side with the official GTT schedule
- Anomaly detection with a queue-based design ready for a future consumer service
- Simple API key authentication for all endpoints

---

## Architecture

```mermaid
graph TD
    subgraph Hardware["Hardware Layer (Local WiFi)"]
        BUS[Bus APC Unit\nArduino]
        STOP[Bus Stop Camera\nArduino]
    end

    subgraph Server["Central Server (FastAPI)"]
        INGEST_BUS[POST /ingest/bus-event]
        INGEST_STOP[POST /ingest/stop-event]
        CORRELATOR[Event Correlator\nmatches bus↔stop events]
        PREDICTOR[Prediction Engine\nML + Rule-based]
        ANOMALY[Anomaly Detector]
        QUEUE[Anomaly Queue Table\nready for consumer]
        API_OUT[Output API\nGET /stops/{id}/status\nGET /buses/{id}/route-forecast]
    end

    subgraph DB["SQLite Database"]
        T1[(bus_events)]
        T2[(stop_events)]
        T3[(correlated_events)]
        T4[(predictions)]
        T5[(anomaly_queue)]
        T6[(routes & stops & schedule)]
    end

    BUS -->|POST JSON + API Key| INGEST_BUS
    STOP -->|POST JSON + API Key| INGEST_STOP
    INGEST_BUS --> CORRELATOR
    INGEST_STOP --> CORRELATOR
    CORRELATOR --> T3
    CORRELATOR --> PREDICTOR
    PREDICTOR --> T4
    PREDICTOR --> ANOMALY
    ANOMALY --> T5
    INGEST_BUS --> T1
    INGEST_STOP --> T2
    API_OUT --> T4
    API_OUT --> T6
```

---

## Data Flow: The Correlation Logic

When a bus leaves a stop, a `bus_event` is stored. The server then waits for a matching `stop_event` from the same stop (within a 30-second window). Once both arrive, the correlator computes:

- `people_boarded` = bus occupancy after − bus occupancy before
- `people_alighted` = stop crowd before − stop crowd after − people boarded
- `dwell_time_actual` = time between door open and door close

This correlated data feeds the prediction engine to update the forecast for all upcoming stops on the bus's route.

```
BUS leaves Stop X  →  bus_event stored  →  wait for stop_event from Stop X
                                            (within 30s window)
                                                ↓
                                    Correlator computes:
                                    - people_boarded
                                    - people_alighted
                                    - dwell_time_actual
                                                ↓
                                    Predictor updates forecast for
                                    all upcoming stops on this bus's route
```

---

## Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| Web Framework | FastAPI | Async, fast, auto OpenAPI docs, ideal for IoT ingestion |
| Database | SQLite (dev) → PostgreSQL-ready | Zero setup for hackathon, SQLAlchemy makes migration trivial |
| ORM | SQLAlchemy | Clean models, DB-agnostic |
| ML Engine | scikit-learn (GradientBoostingRegressor) | Lightweight, no GPU, trains in seconds on simulated data |
| Background Jobs | APScheduler | Runs periodic tasks (model retraining, simulation ticks) |
| Data Generation | pandas + numpy | Simulation and feature engineering |
| Auth | API Key (X-API-Key header) | Simple, secure enough for local WiFi hackathon context |

---

## Project Structure

```
HackTurin/
├── app/
│   ├── main.py                  # FastAPI app entrypoint
│   ├── config.py                # Settings, API keys, constants
│   ├── db/
│   │   ├── database.py          # SQLAlchemy engine & session
│   │   └── init_db.py           # Table creation script
│   ├── models/
│   │   ├── route.py             # Route, Stop, Bus, Schedule models
│   │   ├── events.py            # BusEvent, StopEvent, CorrelatedEvent
│   │   ├── predictions.py       # Prediction model
│   │   └── anomaly.py           # AnomalyQueue model
│   ├── schemas/
│   │   ├── ingest.py            # Pydantic schemas for incoming data
│   │   └── output.py            # Pydantic schemas for API responses
│   ├── routers/
│   │   ├── ingest.py            # POST /ingest/bus-event, /ingest/stop-event
│   │   ├── public.py            # GET /stops/{id}/status, /buses/{id}/route-forecast
│   │   └── admin.py             # GET /admin/anomalies
│   ├── services/
│   │   ├── correlator.py        # Event correlation logic
│   │   ├── predictor.py         # ML prediction engine
│   │   ├── eta_calculator.py    # ETA adjustment logic
│   │   └── anomaly_detector.py  # Anomaly detection rules
│   └── middleware/
│       └── auth.py              # API key authentication middleware
├── simulator/
│   ├── simulate_day.py          # Generate a full day of historical data
│   └── live_feed.py             # Stream live events to the server in real-time
├── ml/
│   ├── train.py                 # Model training script
│   └── model.joblib             # Serialized trained model (auto-generated)
├── seeder.py                    # Populate DB with routes, stops, buses, schedules
├── demo.ps1                     # Windows one-command demo script
├── requirements.txt
├── transport.db                 # SQLite database (auto-created)
└── README.md
```

---

## Setup & Installation

### Prerequisites
- Python 3.11+
- pip

### Steps

```bash
# 1. Navigate to the project directory
cd HackTurin

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize the database
python -m app.db.init_db

# 5. Seed routes, stops, buses & baseline schedule
python seeder.py

# 6. Train the ML model on simulated historical data
python ml/train.py

# 7. Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at `http://localhost:8000`.  
Interactive API docs (Swagger UI) at `http://localhost:8000/docs`.

---

## Running the Demo

```powershell
# Windows — starts server + live simulator + demo API calls in one command
.\demo.ps1
```

Or manually across three terminals:

```bash
# Terminal 1 — start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — stream live simulated events (1 real second = 1 simulated minute)
python simulator/live_feed.py --speed 60

# Terminal 3 — query the API
curl -H "X-API-Key: dev-key" http://localhost:8000/stops/S05/status
```

---

## API Reference

### Authentication

All endpoints (except `/health`) require the following header:

```
X-API-Key: <your-api-key>
```

Default dev key: `dev-key` (configurable in `app/config.py`)

---

### Ingestion Endpoints
> Called by Arduino hardware devices over local WiFi

#### `POST /ingest/bus-event`
Called by the bus APC unit every time the bus closes its doors and leaves a stop.

**Request body:**
```json
{
  "bus_id": "BUS-01",
  "route_id": "R1",
  "stop_id": "S05",
  "timestamp": "2024-01-15T08:32:00Z",
  "passengers_onboard": 34,
  "door_status": "closed",
  "speed_kmh": 0,
  "latitude": 45.0703,
  "longitude": 7.6869
}
```

#### `POST /ingest/stop-event`
Called by the bus stop camera/sensor every 60 seconds, and as a triggered event on bus arrival/departure.

**Request body:**
```json
{
  "stop_id": "S05",
  "timestamp": "2024-01-15T08:32:10Z",
  "people_waiting": 4,
  "event_type": "post_departure"
}
```

`event_type` values: `"periodic"` | `"pre_arrival"` | `"post_departure"`

---

### Public Endpoints
> Called by the citizen mobile app and physical stop displays

#### `GET /stops/{stop_id}/status`
Returns upcoming buses, their ETAs, and predicted crowdedness for a specific stop.

**Response example:**
```json
{
  "stop_id": "S05",
  "stop_name": "Corso Vittorio Emanuele II",
  "current_waiting": 7,
  "next_buses": [
    {
      "bus_id": "BUS-01",
      "route_id": "R1",
      "gtt_eta": "14:32",
      "adjusted_eta": "14:35",
      "eta_delay_minutes": 3,
      "predicted_occupancy_on_arrival_pct": 62,
      "predicted_occupancy_on_departure_pct": 81,
      "crowdedness_on_arrival": "MEDIUM",
      "crowdedness_on_departure": "HIGH",
      "seats_available_on_arrival": 28,
      "route_forecast": [
        {"stop_id": "S06", "stop_name": "Piazza Castello", "predicted_occupancy_pct": 85},
        {"stop_id": "S07", "stop_name": "Via Roma", "predicted_occupancy_pct": 72}
      ]
    }
  ]
}
```

**Crowdedness labels:**

| % Occupancy | Label |
|---|---|
| 0 – 40% | LOW |
| 41 – 65% | MEDIUM |
| 66 – 85% | HIGH |
| 86 – 100% | FULL |

#### `GET /buses/{bus_id}/route-forecast`
Returns the full stop-by-stop occupancy forecast for a bus's remaining route.

#### `GET /health`
Health check endpoint. No authentication required. Returns `{"status": "ok"}`.

---

### Admin Endpoints

#### `GET /admin/anomalies?status=PENDING`
Returns a paginated list of detected anomalies. Requires admin API key.

**Response example:**
```json
{
  "anomalies": [
    {
      "id": 42,
      "anomaly_type": "OVERCROWDING",
      "severity": "HIGH",
      "route_id": "R1",
      "stop_id": "S12",
      "bus_id": "BUS-01",
      "description": "Bus at 95% capacity with 11 people still waiting at stop",
      "status": "PENDING",
      "created_at": "2024-01-15T08:45:00Z",
      "payload": {}
    }
  ],
  "total": 1,
  "page": 1
}
```

---

## Prediction Engine

### Crowdedness Prediction

The ML model (`GradientBoostingRegressor`) is trained on simulated historical data using the following features:

- Current bus occupancy (%)
- Stop index on route
- Time of day (hour)
- Day of week
- Historical average boarding count at the target stop
- Current people waiting at upcoming stops (real-time)
- Rolling average dwell times

It outputs occupancy % **on arrival** and **on departure** for each upcoming stop on the route, giving passengers a complete picture of how crowded their bus will be throughout its journey.

### ETA Adjustment

The adjusted ETA adds predicted boarding delays on top of the GTT baseline schedule:

```
adjusted_dwell = base_dwell + (predicted_boarders × avg_seconds_per_passenger)
adjusted_eta   = gtt_scheduled_time + Σ(dwell_overruns at all stops before target)
```

Average boarding time: **~3 seconds per passenger**.

The API returns both `gtt_eta` (the official schedule) and `adjusted_eta` side by side so passengers and operators can see the real expected delay.

---

## Anomaly Detection

| Anomaly Type | Trigger Condition | Severity |
|---|---|---|
| `OVERCROWDING` | Bus occupancy > 90% AND people still waiting at stop | HIGH |
| `ABNORMAL_CROWD` | Stop waiting count grew > 50% vs 10-min rolling average | MEDIUM |
| `ABANDONMENT` | Stop count drops significantly without a bus arriving | LOW |

Anomalies are stored with `status: "PENDING"` in the `anomaly_queue` table. A future consumer service can poll this table and set `status: "PROCESSED"` when handled. This design follows a simple **outbox/queue pattern** for loose coupling — the central server never needs to know what the consumer does with the alert.

---

## Connecting Arduino Devices

The Arduino boards run Linux (Debian-based, from the HackTurin kit) and communicate with the server over local WiFi via standard HTTP POST requests.

**Example Python snippet for the bus APC unit:**

```python
import requests

SERVER_URL = "http://192.168.1.100:8000"  # Replace with your server's local IP
API_KEY = "your-api-key"

def send_bus_event(bus_id, stop_id, passengers_onboard, lat, lon):
    payload = {
        "bus_id": bus_id,
        "route_id": "R1",
        "stop_id": stop_id,
        "passengers_onboard": passengers_onboard,
        "door_status": "closed",
        "latitude": lat,
        "longitude": lon
    }
    response = requests.post(
        f"{SERVER_URL}/ingest/bus-event",
        json=payload,
        headers={"X-API-Key": API_KEY},
        timeout=5
    )
    return response.json()
```

Find the server's local IP:
- **Windows**: run `ipconfig` → look for *IPv4 Address* (e.g., `192.168.1.100`)
- **Linux/Mac**: run `ip addr` or `ifconfig`

---

## Network Setup (Hackathon)

```
[Arduino Bus Unit]  ──┐
                      ├── Local WiFi Network ──── [Server PC  :8000]
[Arduino Stop Unit] ──┘
```

1. Connect all devices (server PC + Arduino boards) to the **same WiFi network**
2. Find the server PC's local IP (`ipconfig`)
3. Set `SERVER_URL = "http://<server-ip>:8000"` in the Arduino scripts
4. Set the same `API_KEY` value on all devices and in `app/config.py`
5. The server binds to `0.0.0.0` so it accepts connections from any device on the network

---

## Simulation & Demo Data

The project includes a full data simulator that generates realistic Turin bus network data without requiring live hardware.

**Simulated network:**
- 2 routes, 40 stops each (Turin area coordinates)
- 3 buses: 1 on Route 1, 2 on Route 2
- Bus capacity: 75 passengers

**Realistic patterns:**
- Rush hours: high boarding at 07:30–09:00 and 17:30–19:00
- Off-peak: low boarding midday and late evening
- Capacity constraints always respected (never > 75 passengers)
- Consistent boarding math across all events

```bash
# Generate a full simulated day and write to DB
python simulator/simulate_day.py --date 2024-01-15 --output-to-db

# Stream live events to the running server (1 real second = 1 simulated minute)
python simulator/live_feed.py --speed 60
```

---

## Implementation Tasks

The project was built incrementally following these tasks:

1. **Task 1** — Project scaffold & all SQLAlchemy database models
2. **Task 2** — Route, stop & schedule seed data (2 routes, 40 stops, 3 buses, GTT baseline timetable)
3. **Task 3** — Ingestion API endpoints + API key authentication middleware
4. **Task 4** — Event correlator (matches bus↔stop events, computes boarding/alighting)
5. **Task 5** — Data simulator (full day historical + real-time live feed)
6. **Task 6** — ML prediction engine (GradientBoostingRegressor, trained on simulated data)
7. **Task 7** — ETA adjustment engine (GTT baseline + boarding delay calculation)
8. **Task 8** — Anomaly detection (3 rules, queue-based storage for future consumer)
9. **Task 9** — Output API (citizen & display endpoints, admin anomaly endpoint)
10. **Task 10** — Integration, demo script, and full README

---

## Future Extensions

- Replace SQLite with PostgreSQL for multi-server / cloud deployment
- Add a WebSocket endpoint for real-time push to stop displays (instead of polling)
- Build the anomaly consumer service that reads `anomaly_queue` and dispatches alerts (SMS, email, operator dashboard)
- Integrate a real GTFS feed to replace synthetic schedule data
- Retrain the ML model nightly on accumulated real-world data
- Add GPS tracking endpoint so the map view can show live bus positions

---

## License

MIT License — HackTurin 2024
