"""Event correlation.

When a bus leaves a stop (BusEvent) and the stop reports its crowd before and
after (StopEvent with event_type pre_arrival / post_departure), we match them
into a CorrelatedEvent that captures how many people boarded and alighted and
how long the bus dwelled.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import CORRELATION_WINDOW_SECONDS, SECONDS_PER_ALIGHTING, SECONDS_PER_BOARDING, BASE_DWELL_SECONDS
from app.models.events import BusEvent, CorrelatedEvent, StopEvent
from app.models.route import Stop


def _nearest_stop_event(
    db: Session, stop_id: str, around, event_type: str, window: int
) -> StopEvent | None:
    """Find the stop event of a given type closest in time to `around`."""
    low = around - timedelta(seconds=window)
    high = around + timedelta(seconds=window)
    stmt = (
        select(StopEvent)
        .where(
            StopEvent.stop_id == stop_id,
            StopEvent.event_type == event_type,
            StopEvent.timestamp >= low,
            StopEvent.timestamp <= high,
        )
        .order_by(StopEvent.timestamp)
    )
    candidates = db.scalars(stmt).all()
    if not candidates:
        return None
    return min(candidates, key=lambda e: abs((e.timestamp - around).total_seconds()))


def correlate_for_bus_event(db: Session, bus_event: BusEvent) -> CorrelatedEvent | None:
    """Try to build a CorrelatedEvent for a freshly stored bus departure.

    Needs a `pre_arrival` stop event (crowd before boarding) and a
    `post_departure` stop event (crowd left behind) near the bus timestamp.
    Also needs the previous bus departure from the SAME bus to know the
    occupancy before this stop.
    """
    # Avoid creating a duplicate correlation for the same (bus, stop, timestamp).
    existing = db.scalars(
        select(CorrelatedEvent).where(
            CorrelatedEvent.bus_id == bus_event.bus_id,
            CorrelatedEvent.stop_id == bus_event.stop_id,
            CorrelatedEvent.timestamp == bus_event.timestamp,
        )
    ).first()
    if existing is not None:
        return existing

    pre = _nearest_stop_event(
        db, bus_event.stop_id, bus_event.timestamp, "pre_arrival", CORRELATION_WINDOW_SECONDS
    )
    post = _nearest_stop_event(
        db, bus_event.stop_id, bus_event.timestamp, "post_departure", CORRELATION_WINDOW_SECONDS
    )
    if pre is None or post is None:
        return None

    # Occupancy before this stop = occupancy at the bus's last departure from a
    # DIFFERENT (earlier) stop. Using the stop sequence avoids being fooled by
    # repeated events for the current stop.
    this_stop = db.get(Stop, bus_event.stop_id)
    current_seq = this_stop.sequence if this_stop else None

    prev = None
    if current_seq is not None:
        prev_stmt = (
            select(BusEvent)
            .join(Stop, Stop.id == BusEvent.stop_id)
            .where(
                BusEvent.bus_id == bus_event.bus_id,
                Stop.sequence < current_seq,
            )
            .order_by(Stop.sequence.desc(), BusEvent.id.desc())
            .limit(1)
        )
        prev = db.scalars(prev_stmt).first()
    occupancy_before = prev.passengers_onboard if prev else bus_event.passengers_onboard
    occupancy_after = bus_event.passengers_onboard

    waiting_before = pre.people_waiting
    waiting_after = post.people_waiting

    people_boarded = max(0, occupancy_after - occupancy_before)
    # People that got off = those who left the vehicle. We infer alighting from
    # the net change; it cannot be negative.
    people_alighted = max(0, occupancy_before + people_boarded - occupancy_after)

    dwell = BASE_DWELL_SECONDS + people_boarded * SECONDS_PER_BOARDING + people_alighted * SECONDS_PER_ALIGHTING

    correlated = CorrelatedEvent(
        bus_id=bus_event.bus_id,
        route_id=bus_event.route_id,
        stop_id=bus_event.stop_id,
        timestamp=bus_event.timestamp,
        occupancy_before=occupancy_before,
        occupancy_after=occupancy_after,
        waiting_before=waiting_before,
        waiting_after=waiting_after,
        people_boarded=people_boarded,
        people_alighted=people_alighted,
        dwell_time_seconds=dwell,
    )
    db.add(correlated)
    db.commit()
    db.refresh(correlated)
    return correlated


def correlate_for_stop_event(db: Session, stop_event: StopEvent) -> CorrelatedEvent | None:
    """Try to correlate when a stop reports its post-departure crowd.

    The `post_departure` event is usually the LAST piece to arrive, so this is
    the natural trigger. We find the bus departure at the same stop within the
    correlation window and run the normal correlation on it.
    """
    if stop_event.event_type != "post_departure":
        return None

    bus_event = db.scalars(
        select(BusEvent)
        .where(
            BusEvent.stop_id == stop_event.stop_id,
            BusEvent.timestamp >= stop_event.timestamp - timedelta(seconds=CORRELATION_WINDOW_SECONDS),
            BusEvent.timestamp <= stop_event.timestamp + timedelta(seconds=CORRELATION_WINDOW_SECONDS),
        )
        .order_by(BusEvent.id.desc())
        .limit(1)
    ).first()
    if bus_event is None:
        return None
    return correlate_for_bus_event(db, bus_event)
