"""Stream simulated events to a RUNNING server over HTTP.

Mimics the Arduino devices posting to the ingestion API in real time. Useful
for live demos: start the server, then run this.

Run with:
    python -m simulator.live_feed --server http://localhost:8000 --speed 60
"""
from __future__ import annotations

import argparse
import random
import time
from datetime import datetime, timezone

import requests

from app.config import API_KEY, BASE_DWELL_SECONDS, BUS_CAPACITY, ROUTES, STOPS_PER_ROUTE
from simulator.patterns import alighters_for, boarders_for

INTER_STOP_SECONDS = 150


def _stop_id(route_id: str, seq: int) -> str:
    return f"{route_id}-S{seq:02d}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(server: str, speed: float, seed: int = 11, trips: int = 2) -> None:
    rng = random.Random(seed)
    headers = {"X-API-Key": API_KEY}
    session = requests.Session()

    def post(path: str, body: dict) -> None:
        try:
            r = session.post(f"{server}{path}", json=body, headers=headers, timeout=5)
            tag = r.json().get("message") if r.ok else f"HTTP {r.status_code}"
            print(f"  -> {path} {body.get('bus_id') or body.get('stop_id')} "
                  f"({tag or 'ok'})")
        except requests.RequestException as exc:
            print(f"  !! failed POST {path}: {exc}")

    # Interleave all buses so the demo looks live across the network.
    buses = [(rid, bid) for rid, meta in ROUTES.items() for bid in meta["buses"]]
    occupancy = {bid: 0 for _, bid in buses}

    for trip in range(trips):
        for seq in range(STOPS_PER_ROUTE):
            hour = (datetime.now().hour + seq / STOPS_PER_ROUTE) % 24
            for route_id, bus_id in buses:
                stop_id = _stop_id(route_id, seq)
                occ = occupancy[bus_id]

                alight = alighters_for(occ, seq, STOPS_PER_ROUTE, rng)
                occ_after_alight = occ - alight
                waiting = boarders_for(hour, seq, STOPS_PER_ROUTE, rng)
                boarded = min(waiting, BUS_CAPACITY - occ_after_alight)
                occ_after = occ_after_alight + boarded
                occupancy[bus_id] = occ_after

                # pre_arrival: crowd before the bus boards them
                post("/ingest/stop-event", {
                    "stop_id": stop_id,
                    "timestamp": _now_iso(),
                    "people_waiting": waiting,
                    "event_type": "pre_arrival",
                })
                # bus departs
                post("/ingest/bus-event", {
                    "bus_id": bus_id,
                    "route_id": route_id,
                    "stop_id": stop_id,
                    "timestamp": _now_iso(),
                    "passengers_onboard": occ_after,
                    "door_status": "closed",
                })
                # post_departure: crowd left behind
                post("/ingest/stop-event", {
                    "stop_id": stop_id,
                    "timestamp": _now_iso(),
                    "people_waiting": waiting - boarded,
                    "event_type": "post_departure",
                })

            # Compress simulated inter-stop travel time by `speed`.
            time.sleep(max(0.0, (INTER_STOP_SECONDS + BASE_DWELL_SECONDS) / speed))

    print("Live feed finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stream live events to the server.")
    parser.add_argument("--server", default="http://localhost:8000")
    parser.add_argument("--speed", type=float, default=60.0, help="simulated seconds per real second")
    parser.add_argument("--trips", type=int, default=2)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()
    run(args.server, args.speed, args.seed, args.trips)
