"""Stored crowdedness predictions for upcoming stops."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.config import utcnow
from app.db.database import Base


class Prediction(Base):
    """A forecast of how full a bus will be at a given upcoming stop."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bus_id: Mapped[str] = mapped_column(ForeignKey("buses.id"), index=True)
    route_id: Mapped[str] = mapped_column(String, index=True)
    target_stop_id: Mapped[str] = mapped_column(ForeignKey("stops.id"), index=True)

    predicted_occupancy_on_arrival: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_occupancy_on_departure: Mapped[float] = mapped_column(Float, nullable=False)

    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
