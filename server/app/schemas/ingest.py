"""Pydantic schemas for data coming IN from devices."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class BusEventIn(BaseModel):
    """APC payload sent by a bus on door-close / departure."""

    bus_id: str = Field(..., examples=["BUS-01"])
    route_id: str = Field(..., examples=["R1"])
    stop_id: str = Field(..., examples=["S05"])
    timestamp: Optional[datetime] = Field(
        default=None, description="Event time; server fills now() if omitted."
    )
    passengers_onboard: int = Field(..., ge=0, examples=[34])
    door_status: Literal["open", "closed"] = "closed"
    speed_kmh: float = Field(default=0.0, ge=0)
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class StopEventIn(BaseModel):
    """Camera/sensor payload from a bus stop."""

    stop_id: str = Field(..., examples=["S05"])
    timestamp: Optional[datetime] = Field(default=None)
    people_waiting: int = Field(..., ge=0, examples=[4])
    event_type: Literal["periodic", "pre_arrival", "post_departure"] = "periodic"


class IngestAck(BaseModel):
    """Standard acknowledgement returned by ingestion endpoints."""

    status: str = "ok"
    stored_id: int
    correlated: bool = False
    message: Optional[str] = None
