"""Pydantic schemas for data going OUT to the app / displays / admin."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RouteForecastStop(BaseModel):
    stop_id: str
    stop_name: str
    predicted_occupancy_pct: int


class NextBus(BaseModel):
    bus_id: str
    route_id: str
    gtt_eta: str
    adjusted_eta: str
    eta_delay_minutes: int
    predicted_occupancy_on_arrival_pct: int
    predicted_occupancy_on_departure_pct: int
    crowdedness_on_arrival: str
    crowdedness_on_departure: str
    seats_available_on_arrival: int
    route_forecast: list[RouteForecastStop]


class StopStatus(BaseModel):
    stop_id: str
    stop_name: str
    current_waiting: int
    next_buses: list[NextBus]


class BusRouteForecast(BaseModel):
    bus_id: str
    route_id: str
    current_occupancy_pct: int
    forecast: list[RouteForecastStop]


class AnomalyOut(BaseModel):
    id: int
    anomaly_type: str
    severity: str
    route_id: Optional[str]
    stop_id: Optional[str]
    bus_id: Optional[str]
    description: str
    status: str
    created_at: datetime
    payload: dict

    model_config = ConfigDict(from_attributes=True)


class AnomalyList(BaseModel):
    anomalies: list[AnomalyOut]
    total: int
    page: int
