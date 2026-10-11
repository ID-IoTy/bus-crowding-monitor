"""Shared helpers to build a tiny network inside tests."""
from __future__ import annotations

from app.config import BUS_CAPACITY
from app.models.route import Bus, Route, Schedule, Stop


def build_small_network(db, stops: int = 6) -> None:
    """One route (RT) with `stops` stops and one bus (BUS-T)."""
    db.add(Route(id="RT", name="Test Route"))
    for seq in range(stops):
        db.add(Stop(
            id=f"RT-S{seq:02d}",
            route_id="RT",
            name=f"Stop {seq}",
            sequence=seq,
            latitude=45.0 + seq * 0.001,
            longitude=7.0 + seq * 0.001,
        ))
    db.add(Bus(id="BUS-T", route_id="RT", capacity=BUS_CAPACITY))
    # Minimal schedule: 100s between stops starting at 08:00.
    for seq in range(stops):
        db.add(Schedule(
            bus_id="BUS-T",
            route_id="RT",
            stop_id=f"RT-S{seq:02d}",
            trip_number=0,
            scheduled_seconds=8 * 3600 + seq * 100,
        ))
    db.commit()
