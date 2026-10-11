"""Shared, validated wire contracts. Counts are snapshots, not passenger throughput."""
from datetime import datetime
from typing import Annotated, Literal, Protocol

from pydantic import AfterValidator, BaseModel, Field


def aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return value


Timestamp = Annotated[datetime, AfterValidator(aware)]
Count = Annotated[int, Field(ge=0)]


class VehicleApproach(BaseModel):
    event_id: str
    vehicle_id: str
    trip_id: str
    line_id: str
    direction: str
    next_stop_id: str
    stop_sequence: Count
    eta_s: Count
    lat: float
    lon: float
    onboard: Count
    sim_time: Timestamp


class VehicleDeparture(BaseModel):
    event_id: str
    vehicle_id: str
    trip_id: str
    line_id: str
    direction: str
    stop_id: str
    stop_sequence: Count
    arrived_at: Timestamp
    doors_closed_at: Timestamp
    boarded: Count
    alighted: Count
    onboard: Count
    lat: float
    lon: float
    is_terminus: bool


class CameraObservation(BaseModel):
    observation_id: str
    camera_id: str
    stop_id: str
    source: Literal["simulated", "physical"]
    measured_at: Timestamp
    waiting_count: Count
    trigger: Literal["periodic", "pre_arrival", "post_departure"]
    request_id: str | None = None
    visit_id: str | None = None
    device_measured_at: Timestamp | None = None


class CountRequest(BaseModel):
    request_id: str
    visit_id: str
    reason: Literal["pre_arrival", "post_departure"]
    delay_s: Count = 0


class EdgeCount(BaseModel):
    count: Count
    measured_at: Timestamp


class DisplayBus(BaseModel):
    line_id: str
    eta_s: int
    predicted_onboard: float
    interval_80: tuple[float, float]
    level: Literal["green", "yellow", "orange", "red"]
    confidence: float | None = None
    may_not_fit: bool


class DisplayPayload(BaseModel):
    stop_id: str
    generated_at: Timestamp
    buses: list[DisplayBus]


class ClockCommand(BaseModel):
    speed: float | None = Field(default=None, ge=1, le=60)
    paused: bool | None = None


class ScenarioCommand(BaseModel):
    name: Literal["normal", "rush_hour", "overcrowding"]


class CameraModeCommand(BaseModel):
    mode: Literal["simulated", "physical"]


class WsEnvelope(BaseModel):
    type: Literal["clock", "vehicles", "stops", "predictions", "alerts"]
    sim_time: Timestamp
    data: dict


class IngestPort(Protocol):
    def approach(self, event: VehicleApproach) -> str: ...
    def departure(self, event: VehicleDeparture) -> str: ...
    def observation(self, event: CameraObservation) -> str: ...


class CameraPort(Protocol):
    def count_request(self, camera_id: str, request: CountRequest) -> None: ...
    def display(self, camera_id: str, payload: DisplayPayload) -> None: ...
