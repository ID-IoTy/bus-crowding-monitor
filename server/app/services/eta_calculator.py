"""Adjusted ETA engine.

GTT publishes a baseline timetable that assumes a fixed, optimistic dwell at
each stop. Our adjusted ETA adds the EXTRA boarding time predicted for the
upcoming crowds, so passengers see a realistic arrival time.

We return both the GTT baseline and our adjusted figure so they can be
compared side by side.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BASE_DWELL_SECONDS, SECONDS_PER_BOARDING
from app.models.route import Bus, Schedule, Stop
from app.services.predictor import StopForecast


def _scheduled_seconds(db: Session, bus_id: str, stop_id: str) -> int | None:
    """Earliest scheduled arrival (seconds from midnight) for a bus at a stop."""
    row = db.scalars(
        select(Schedule)
        .where(Schedule.bus_id == bus_id, Schedule.stop_id == stop_id)
        .order_by(Schedule.scheduled_seconds)
        .limit(1)
    ).first()
    return row.scheduled_seconds if row else None


def adjusted_eta_seconds(
    db: Session,
    bus_id: str,
    target_stop_id: str,
    forecasts: list[StopForecast],
    current_sequence: int,
    now: datetime | None = None,
) -> tuple[int | None, int | None]:
    """Return (gtt_seconds, adjusted_seconds) for the bus reaching target stop.

    The adjustment is the GTT baseline plus the cumulative EXTRA dwell caused by
    predicted boarders at every stop strictly between the bus and the target.
    """
    gtt = _scheduled_seconds(db, bus_id, target_stop_id)
    if gtt is None:
        return None, None

    bus = db.get(Bus, bus_id)
    target = db.scalars(
        select(Stop).where(Stop.id == target_stop_id, Stop.route_id == bus.route_id)
    ).first()
    if target is None:
        return gtt, gtt

    capacity = bus.capacity

    extra_seconds = 0.0
    for fc in forecasts:
        if fc.sequence >= target.sequence:
            break  # only stops before the target add boarding delay
        boarders = (fc.occupancy_on_departure - fc.occupancy_on_arrival) * capacity
        # GTT already bakes in BASE_DWELL_SECONDS; we only add the boarding part
        # that exceeds what the baseline assumed.
        extra_seconds += max(0.0, boarders * SECONDS_PER_BOARDING)

    adjusted = int(round(gtt + extra_seconds))
    return gtt, adjusted
