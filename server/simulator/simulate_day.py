"""Generate a full day of historical data straight into the database.

This produces consistent bus_events, stop_events and correlated_events so the
ML model has something to train on and the API has history to serve.

Run with:
    python -m simulator.simulate_day --date 2024-01-15
"""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta

from sqlalchemy import select

from app.config import (
    BASE_DWELL_SECONDS,
    BUS_CAPACITY,
    ROUTES,
    SECONDS_PER_ALIGHTING,
    SECONDS_PER_BOARDING,
    STOPS_PER_ROUTE,
)
from app.db.database import Base, SessionLocal, engine
import app.models  # noqa: F401
from app.models.events import BusEvent, CorrelatedEvent, StopEvent
from app.models.route import Bus, Stop
from simulator.patterns import alighters_for, boarders_for

INTER_STOP_SECONDS = 150
TRIPS_PER_BUS = 8
FIRST_DEPARTURE_SECONDS = 6 * 3600
TRIP_INTERVAL_SECONDS = 45 * 60


def _stop_id(route_id: str, seq: int) -> str:
    return f"{route_id}-S{seq:02d}"


def simulate(date_str: str, seed: int = 7) -> None:
    rng = random.Random(seed)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d")

        # Wipe previous event history (keep topology & schedule).
        for model in (CorrelatedEvent, BusEvent, StopEvent):
            db.query(model).delete()
        db.commit()

        n_bus_events = n_stop_events = n_correlated = 0

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

                        waiting_before = boarders_for(hour, seq, STOPS_PER_ROUTE, rng)
                        free = BUS_CAPACITY - occ_after_alight
                        boarded = min(waiting_before, free)
                        waiting_after = waiting_before - boarded
                        occupancy_after = occ_after_alight + boarded

                        dwell = (
                            BASE_DWELL_SECONDS
                            + boarded * SECONDS_PER_BOARDING
                            + alight * SECONDS_PER_ALIGHTING
                        )

                        # pre_arrival stop event (crowd waiting before boarding)
                        db.add(StopEvent(
                            stop_id=stop_id,
                            timestamp=ts - timedelta(seconds=5),
                            people_waiting=waiting_before,
                            event_type="pre_arrival",
                        ))
                        n_stop_events += 1

                        # bus departs
                        db.add(BusEvent(
                            bus_id=bus_id,
                            route_id=route_id,
                            stop_id=stop_id,
                            timestamp=ts,
                            passengers_onboard=occupancy_after,
                            door_status="closed",
                            speed_kmh=0.0,
                        ))
                        n_bus_events += 1

                        # post_departure stop event (crowd left behind)
                        db.add(StopEvent(
                            stop_id=stop_id,
                            timestamp=ts + timedelta(seconds=10),
                            people_waiting=waiting_after,
                            event_type="post_departure",
                        ))
                        n_stop_events += 1

                        # correlated record (ground truth for training)
                        db.add(CorrelatedEvent(
                            bus_id=bus_id,
                            route_id=route_id,
                            stop_id=stop_id,
                            timestamp=ts,
                            occupancy_before=occupancy,
                            occupancy_after=occupancy_after,
                            waiting_before=waiting_before,
                            waiting_after=waiting_after,
                            people_boarded=boarded,
                            people_alighted=alight,
                            dwell_time_seconds=dwell,
                        ))
                        n_correlated += 1

                        occupancy = occupancy_after

        db.commit()
        print("Simulation complete:")
        print(f"  bus_events:        {n_bus_events}")
        print(f"  stop_events:       {n_stop_events}")
        print(f"  correlated_events: {n_correlated}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate a day of transport data.")
    parser.add_argument("--date", default="2024-01-15", help="Simulated date YYYY-MM-DD")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    simulate(args.date, args.seed)
