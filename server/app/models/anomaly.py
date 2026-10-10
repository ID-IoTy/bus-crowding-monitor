"""Anomaly queue - an outbox table a future consumer service can poll."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.config import utcnow
from app.db.database import Base


class AnomalyQueue(Base):
    """Detected anomalies awaiting processing by an external consumer.

    The central server only ever *writes* PENDING rows here. A separate
    service (not part of this project) reads them and flips status to
    PROCESSED. This keeps the two systems loosely coupled.
    """

    __tablename__ = "anomaly_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anomaly_type: Mapped[str] = mapped_column(String, index=True)  # OVERCROWDING|ABNORMAL_CROWD|ABANDONMENT
    severity: Mapped[str] = mapped_column(String, index=True)      # LOW|MEDIUM|HIGH
    route_id: Mapped[str | None] = mapped_column(String, nullable=True)
    stop_id: Mapped[str | None] = mapped_column(String, nullable=True)
    bus_id: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String, default="PENDING", index=True)  # PENDING|PROCESSED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
