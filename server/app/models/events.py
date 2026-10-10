"""Raw ingested events and the correlated result."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.config import utcnow
from app.db.database import Base


class BusEvent(Base):
    """APC payload sent by a bus when it closes its doors and leaves a stop."""

    __tablename__ = "bus_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bus_id: Mapped[str] = mapped_column(ForeignKey("buses.id"), index=True)
    route_id: Mapped[str] = mapped_column(String, index=True)
    stop_id: Mapped[str] = mapped_column(ForeignKey("stops.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    passengers_onboard: Mapped[int] = mapped_column(Integer, nullable=False)
    door_status: Mapped[str] = mapped_column(String, default="closed")
    speed_kmh: Mapped[float] = mapped_column(Float, default=0.0)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StopEvent(Base):
    """Camera/sensor payload from a bus stop."""

    __tablename__ = "stop_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stop_id: Mapped[str] = mapped_column(ForeignKey("stops.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    people_waiting: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String, default="periodic")  # periodic|pre_arrival|post_departure
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CorrelatedEvent(Base):
    """Result of matching a bus departure with the stop's before/after counts."""

    __tablename__ = "correlated_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bus_id: Mapped[str] = mapped_column(ForeignKey("buses.id"), index=True)
    route_id: Mapped[str] = mapped_column(String, index=True)
    stop_id: Mapped[str] = mapped_column(ForeignKey("stops.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)

    occupancy_before: Mapped[int] = mapped_column(Integer, nullable=False)
    occupancy_after: Mapped[int] = mapped_column(Integer, nullable=False)
    waiting_before: Mapped[int] = mapped_column(Integer, nullable=False)
    waiting_after: Mapped[int] = mapped_column(Integer, nullable=False)

    people_boarded: Mapped[int] = mapped_column(Integer, nullable=False)
    people_alighted: Mapped[int] = mapped_column(Integer, nullable=False)
    dwell_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
