"""Generate a week of EXAMPLE API payloads as JSONL files.

The output mirrors exactly the HTTP bodies the Arduino devices would have POSTed
to the server over the previous week:

  server/sample_data/bus_events_week.jsonl   -> POST /ingest/bus-event bodies
  server/sample_data/stop_events_week.jsonl  -> POST /ingest/stop-event bodies

Each line is one JSON object. The two streams are internally consistent (the
onboard counts and the before/after crowd counts line up), so when they are
replayed through the server the correlator reconstructs real boarding/alighting
figures - exactly the `correlated_events` the ML model trains on.

The week runs Mon-Fri at full demand and Sat-Sun lighter, and injects a few
anomalies (near-full buses, abandonment-style drops).

Run with:
    python -m simulator.generate_sample_week --start 2024-01-08
(2024-01-08 is a Monday.)
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from app.config import (
    BASE_DWELL_SECONDS,
    BUS_CAPACITY,
    ROUTES,
    STOPS_PER_ROUTE,
)
from simulator.patterns import alighters_for, boarders_for

INTER_STOP_SECONDS = 150
TRIPS_PER_BUS = 8
FIRST_DEPARTURE_SECONDS = 6 * 3600
TRIP_INTERVAL_SECONDS = 45 * 60

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


def _stop_id(route_id: str, seq: int) -> str:
    return f"{route_id}-S{seq:02d}"


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat() + "Z"


def generate(start_date: str, seed: int = 2024) -> tuple[int, int, int]:
    rng = random.Random(seed)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    start = datetime.strptime(start_date, "%Y-%m-%d")
    bus_lines: list[str] = []
    stop_lines: list[str] = []
    anomalies_injected = 0

    for day_offset in range(7):
        day = start + timedelta(days=day_offset)
        weekday = day.weekday()  # 0=Mon .. 6=Sun

        for route_id, meta in ROUTES.items():
            for bus_offset, bus_id in enumerate(meta["buses"]):
                for trip in range(TRIPS_PER_BUS):
                    trip_start = (
                        FIRST_DEPARTURE_SECONDS
                        + trip * TRIP_INTERVAL_SECONDS
                        + bus_offset * (TRIP_INTERVAL_SECONDS // 2)
                    )
                    occupancy = 0
                    for seq in range(STOPS_PER_ROUTE):
                        arrival_s = trip_start + seq * (INTER_STOP_SECONDS + BASE_DWELL_SECONDS)
                        ts = day + timedelta(seconds=arrival_s)
                        hour = arrival_s / 3600.0
                        stop_id = _stop_id(route_id, seq)

                        alight = alighters_for(occupancy, seq, STOPS_PER_ROUTE, rng)
                        occ_after_alight = occupancy - alight

                        waiting_before = boarders_for(hour, seq, STOPS_PER_ROUTE, rng, weekday)

                        # --- occasional injected anomalies -------------------
                        inject_overcrowd = rng.random() < 0.01 and seq < STOPS_PER_ROUTE - 5
                        if inject_overcrowd:
                            # Force a near-full bus with a big crowd left behind.
                            occ_after_alight = max(occ_after_alight, 68)
                            waiting_before = max(waiting_before, 20)

                        free = BUS_CAPACITY - occ_after_alight
                        boarded = min(waiting_before, free)
                        waiting_after = waiting_before - boarded
                        occupancy_after = occ_after_alight + boarded

                        if inject_overcrowd and waiting_after > 0:
                            anomalies_injected += 1

                        # Abandonment-style anomaly: a lone periodic reading where
                        # the crowd suddenly dropped with no bus (we emit an extra
                        # periodic pair occasionally).
                        inject_abandon = rng.random() < 0.008

                        # pre_arrival stop reading (crowd before boarding)
                        stop_lines.append(json.dumps({
                            "stop_id": stop_id,
                            "timestamp": _iso(ts - timedelta(seconds=5)),
                            "people_waiting": waiting_before,
                            "event_type": "pre_arrival",
                        }))

                        # bus departure (APC)
                        bus_lines.append(json.dumps({
                            "bus_id": bus_id,
                            "route_id": route_id,
                            "stop_id": stop_id,
                            "timestamp": _iso(ts),
                            "passengers_onboard": occupancy_after,
                            "door_status": "closed",
                            "speed_kmh": 0,
                        }))

                        # post_departure stop reading (crowd left behind)
                        stop_lines.append(json.dumps({
                            "stop_id": stop_id,
                            "timestamp": _iso(ts + timedelta(seconds=10)),
                            "people_waiting": waiting_after,
                            "event_type": "post_departure",
                        }))

                        # periodic heartbeat ~30s after departure
                        periodic_waiting = waiting_after
                        if inject_abandon and waiting_after >= 5:
                            periodic_waiting = max(0, waiting_after // 3)  # sudden drop
                            anomalies_injected += 1
                        stop_lines.append(json.dumps({
                            "stop_id": stop_id,
                            "timestamp": _iso(ts + timedelta(seconds=40)),
                            "people_waiting": periodic_waiting,
                            "event_type": "periodic",
                        }))

                        occupancy = occupancy_after

    # Sort each stream by timestamp so the files read like a real time-ordered log.
    bus_lines.sort(key=lambda s: json.loads(s)["timestamp"])
    stop_lines.sort(key=lambda s: json.loads(s)["timestamp"])

    bus_path = SAMPLE_DIR / "bus_events_week.jsonl"
    stop_path = SAMPLE_DIR / "stop_events_week.jsonl"
    bus_path.write_text("\n".join(bus_lines) + "\n", encoding="utf-8")
    stop_path.write_text("\n".join(stop_lines) + "\n", encoding="utf-8")

    return len(bus_lines), len(stop_lines), anomalies_injected


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a week of sample API payloads.")
    parser.add_argument("--start", default="2024-01-08", help="Monday start date YYYY-MM-DD")
    parser.add_argument("--seed", type=int, default=2024)
    args = parser.parse_args()
    n_bus, n_stop, n_anom = generate(args.start, args.seed)
    print("Sample week generated in server/sample_data/:")
    print(f"  bus_events_week.jsonl:  {n_bus} payloads")
    print(f"  stop_events_week.jsonl: {n_stop} payloads")
    print(f"  anomaly scenarios injected: ~{n_anom}")
