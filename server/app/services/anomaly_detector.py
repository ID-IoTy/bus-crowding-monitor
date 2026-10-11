"""Anomaly detection.

Writes PENDING rows into the anomaly_queue outbox table. A separate consumer
service (out of scope here) polls that table and acts on the alerts.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import (
    ABANDONMENT_DROP,
    ABNORMAL_CROWD_GROWTH,
    BUS_CAPACITY,
    OVERCROWDING_OCCUPANCY,
)
from app.models.anomaly import AnomalyQueue
from app.models.events import BusEvent, CorrelatedEvent, StopEvent
from app.models.route import Stop


def _enqueue(db: Session, **kwargs) -> AnomalyQueue:
    anomaly = AnomalyQueue(status="PENDING", **kwargs)
    db.add(anomaly)
    db.commit()
    db.refresh(anomaly)
    return anomaly


def check_overcrowding(db: Session, correlated: CorrelatedEvent) -> AnomalyQueue | None:
    """Bus leaves nearly full while people are still waiting -> HIGH alert."""
    occ_frac = correlated.occupancy_after / BUS_CAPACITY
    if occ_frac >= OVERCROWDING_OCCUPANCY and correlated.waiting_after > 0:
        return _enqueue(
            db,
            anomaly_type="OVERCROWDING",
            severity="HIGH",
            route_id=correlated.route_id,
            stop_id=correlated.stop_id,
            bus_id=correlated.bus_id,
            description=(
                f"Bus at {occ_frac * 100:.0f}% capacity left "
                f"{correlated.waiting_after} people still waiting at stop "
                f"{correlated.stop_id}"
            ),
            payload={
                "occupancy_pct": round(occ_frac * 100),
                "left_behind": correlated.waiting_after,
            },
        )
    return None


def check_abnormal_crowd(db: Session, stop_event: StopEvent) -> AnomalyQueue | None:
    """Stop crowd grew far beyond its recent rolling average -> MEDIUM alert."""
    window_start = stop_event.timestamp - timedelta(minutes=10)
    recent = db.scalars(
        select(StopEvent).where(
            StopEvent.stop_id == stop_event.stop_id,
            StopEvent.timestamp >= window_start,
            StopEvent.timestamp < stop_event.timestamp,
        )
    ).all()
    if len(recent) < 3:
        return None  # not enough history to judge
    avg = sum(e.people_waiting for e in recent) / len(recent)
    if avg <= 0:
        return None
    growth = (stop_event.people_waiting - avg) / avg
    if growth >= ABNORMAL_CROWD_GROWTH and stop_event.people_waiting >= 8:
        return _enqueue(
            db,
            anomaly_type="ABNORMAL_CROWD",
            severity="MEDIUM",
            route_id=_route_of_stop(db, stop_event.stop_id),
            stop_id=stop_event.stop_id,
            bus_id=None,
            description=(
                f"Crowd at stop {stop_event.stop_id} grew {growth * 100:.0f}% "
                f"above its 10-min average (now {stop_event.people_waiting})"
            ),
            payload={
                "current_waiting": stop_event.people_waiting,
                "rolling_avg": round(avg, 1),
                "growth_pct": round(growth * 100),
            },
        )
    return None


def check_abandonment(db: Session, stop_event: StopEvent) -> AnomalyQueue | None:
    """Crowd dropped sharply WITHOUT a bus arriving -> people gave up -> LOW."""
    if stop_event.event_type != "periodic":
        return None  # post_departure drops are expected, not abandonment
    prev = db.scalars(
        select(StopEvent)
        .where(StopEvent.stop_id == stop_event.stop_id, StopEvent.id < stop_event.id)
        .order_by(StopEvent.id.desc())
        .limit(1)
    ).first()
    if prev is None or prev.people_waiting < 5:
        return None
    drop = (prev.people_waiting - stop_event.people_waiting) / prev.people_waiting
    if drop < ABANDONMENT_DROP:
        return None
    # Make sure no bus departed from this stop around the drop.
    window_start = prev.timestamp - timedelta(seconds=30)
    bus_left = db.scalars(
        select(BusEvent).where(
            BusEvent.stop_id == stop_event.stop_id,
            BusEvent.timestamp >= window_start,
            BusEvent.timestamp <= stop_event.timestamp,
        )
    ).first()
    if bus_left is not None:
        return None  # the drop is explained by boarding, not abandonment
    return _enqueue(
        db,
        anomaly_type="ABANDONMENT",
        severity="LOW",
        route_id=_route_of_stop(db, stop_event.stop_id),
        stop_id=stop_event.stop_id,
        bus_id=None,
        description=(
            f"Crowd at stop {stop_event.stop_id} dropped {drop * 100:.0f}% "
            f"with no bus arrival (likely abandonment)"
        ),
        payload={
            "before": prev.people_waiting,
            "after": stop_event.people_waiting,
            "drop_pct": round(drop * 100),
        },
    )


def _route_of_stop(db: Session, stop_id: str) -> str | None:
    stop = db.get(Stop, stop_id)
    return stop.route_id if stop else None
