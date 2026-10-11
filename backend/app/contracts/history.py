"""Operator-only historical observation summaries; not forecast accuracy."""
from datetime import date
from typing import Literal
from pydantic import BaseModel
from app.contracts import Timestamp


class HistoryBucket(BaseModel):
    label: str
    waiting_mean: float | None
    onboard_percent_mean: float | None
    waiting_samples: int
    vehicle_samples: int


class HistoryStop(BaseModel):
    stop_id: str
    name: str
    mean_waiting: float
    peak_waiting: int
    samples: int


class HistorySummary(BaseModel):
    waiting_mean: float | None
    onboard_percent_mean: float | None
    high_load_percent: float | None
    waiting_samples: int
    vehicle_samples: int
    observed_stops: int


class HistoryView(BaseModel):
    generated_at: Timestamp
    source: Literal["synthetic_history"] = "synthetic_history"
    available_from: date | None
    available_to: date | None
    start: date | None
    end: date | None
    route_id: str | None
    stop_id: str | None
    capacity_assumed: int
    summary: HistorySummary
    hourly: list[HistoryBucket]
    daily: list[HistoryBucket]
    busiest_stops: list[HistoryStop]
    notes: list[str]
