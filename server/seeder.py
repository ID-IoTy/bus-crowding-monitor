"""Populate the database with the network topology and a GTT baseline schedule.

Run with:  python seeder.py

Creates:
  - 2 routes, 40 stops each (scattered around Turin)
  - 3 buses (1 on R1, 2 on R2), capacity 75
  - a synthetic GTT timetable: several daily trips per bus, with an optimistic
    fixed dwell at each stop (this is what our adjusted ETA improves upon).
"""
from __future__ import annotations

import math
import random

from app.config import (
    BASE_DWELL_SECONDS,
    BUS_CAPACITY,
    ROUTES,
    STOPS_PER_ROUTE,
    TURIN_LAT,
    TURIN_LON,
)
from app.db.database import Base, SessionLocal, engine
import app.models  # noqa: F401
from app.models.route import Bus, Route, Schedule, Stop

random.seed(42)

# Baseline travel time between consecutive stops (seconds) used by GTT.
INTER_STOP_SECONDS = 150  # ~2.5 min
FIRST_DEPARTURE_SECONDS = 6 * 3600  # 06:00
TRIPS_PER_BUS = 8
TRIP_INTERVAL_SECONDS = 45 * 60  # a new trip every 45 min


def _stop_id(route_id: str, seq: int) -> str:
    return f"{route_id}-S{seq:02d}"


STREET_NAMES = [
    "Via Roma", "Corso Vittorio", "Piazza Castello", "Porta Nuova", "Lingotto",
    "Mirafiori", "Crocetta", "San Salvario", "Vanchiglia", "Cenisia",
    "Barriera", "Pozzo Strada", "Santa Rita", "Nizza", "Dora",
    "Aurora", "Madonna di Campagna", "Parella", "Borgo Po", "Cit Turin",
]


def _stop_name(route_id: str, seq: int) -> str:
    base = STREET_NAMES[seq % len(STREET_NAMES)]
    return f"{base} ({route_id} #{seq:02d})"


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Clean slate for idempotent re-seeding.
        for model in (Schedule, Stop, Bus, Route):
            db.query(model).delete()
        db.commit()

        for r_index, (route_id, meta) in enumerate(ROUTES.items()):
            route = Route(id=route_id, name=meta["name"])
            db.add(route)

            for seq in range(STOPS_PER_ROUTE):
                # Scatter stops along a gentle arc around Turin.
                angle = (seq / STOPS_PER_ROUTE) * math.pi + r_index * 0.5
                lat = TURIN_LAT + 0.03 * math.sin(angle) + r_index * 0.01
                lon = TURIN_LON + 0.04 * (seq / STOPS_PER_ROUTE) - 0.02 + r_index * 0.01
                db.add(
                    Stop(
                        id=_stop_id(route_id, seq),
                        route_id=route_id,
                        name=_stop_name(route_id, seq),
                        sequence=seq,
                        latitude=round(lat, 6),
                        longitude=round(lon, 6),
                    )
                )

            for bus_id in meta["buses"]:
                db.add(Bus(id=bus_id, route_id=route_id, capacity=BUS_CAPACITY))

        db.commit()

        # GTT baseline timetable.
        schedule_rows = 0
        for route_id, meta in ROUTES.items():
            for bus_offset, bus_id in enumerate(meta["buses"]):
                for trip in range(TRIPS_PER_BUS):
                    trip_start = (
                        FIRST_DEPARTURE_SECONDS
                        + trip * TRIP_INTERVAL_SECONDS
                        + bus_offset * (TRIP_INTERVAL_SECONDS // 2)
                    )
                    for seq in range(STOPS_PER_ROUTE):
                        arrival = trip_start + seq * (INTER_STOP_SECONDS + BASE_DWELL_SECONDS)
                        db.add(
                            Schedule(
                                bus_id=bus_id,
                                route_id=route_id,
                                stop_id=_stop_id(route_id, seq),
                                trip_number=trip,
                                scheduled_seconds=arrival,
                            )
                        )
                        schedule_rows += 1
        db.commit()

        n_routes = db.query(Route).count()
        n_stops = db.query(Stop).count()
        n_buses = db.query(Bus).count()
        print("Seed complete:")
        print(f"  routes:   {n_routes}")
        print(f"  stops:    {n_stops}")
        print(f"  buses:    {n_buses}")
        print(f"  schedule: {schedule_rows} rows")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
