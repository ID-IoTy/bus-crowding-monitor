"""Network topology models: Route, Stop, Bus and the baseline Schedule."""
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "R1"
    name: Mapped[str] = mapped_column(String, nullable=False)

    stops: Mapped[list["Stop"]] = relationship(
        back_populates="route", order_by="Stop.sequence", cascade="all, delete-orphan"
    )
    buses: Mapped[list["Bus"]] = relationship(back_populates="route")


class Stop(Base):
    __tablename__ = "stops"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "S05"
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id"), index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-based order on the route
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    route: Mapped[Route] = relationship(back_populates="stops")

    __table_args__ = (UniqueConstraint("route_id", "sequence", name="uq_stop_route_sequence"),)


class Bus(Base):
    __tablename__ = "buses"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "BUS-01"
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id"), index=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    route: Mapped[Route] = relationship(back_populates="buses")


class Schedule(Base):
    """Synthetic GTT baseline timetable.

    One row = the scheduled arrival time (seconds from midnight) of a given
    bus at a given stop on a given trip.
    """

    __tablename__ = "schedule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bus_id: Mapped[str] = mapped_column(ForeignKey("buses.id"), index=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id"), index=True)
    stop_id: Mapped[str] = mapped_column(ForeignKey("stops.id"), index=True)
    trip_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "bus_id", "stop_id", "trip_number", name="uq_schedule_bus_stop_trip"
        ),
    )
