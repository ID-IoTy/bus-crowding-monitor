from typing import Literal
from pydantic import BaseModel
from app.contracts import Timestamp


class Position(BaseModel):
    lat: float
    lon: float


class RouteStop(Position):
    id: str
    name: str


class Route(BaseModel):
    id: str
    routeId: str
    name: str
    description: str
    direction: str
    headsign: str
    color: str
    stops: list[RouteStop]
    shape: list[list[float]]
    offsets: list[int]


class Passage(BaseModel):
    stopId: str
    arrival: Timestamp
    departure: Timestamp
    arriving: int | None
    leaving: int | None
    percent: int | None
    alighting: int
    boarding: int
    leftBehind: int
    may_not_fit: bool = False
    level: str | None = None
    interval_80: list[float] | None = None
    confidence: float | None = None
    reliability: float | None = None
    generated_at: Timestamp | None = None
    kind: Literal["predicted"] = "predicted"
    basis: str | None = None
    model_version: str | None = None


class JourneyTrip(BaseModel):
    id: str
    lineId: str
    vehicleId: str
    startsAt: Timestamp
    capacity: int | None
    seated_capacity: int | None
    passages: list[Passage]
    position: Position
    positionKind: Literal["simulated-current", "predicted", "not-started"]
    observed: dict | None
    reliability: float | None = None


class JourneyOption(BaseModel):
    route: Route
    trips: list[JourneyTrip]
    originIndex: int
    destinationIndex: int


class JourneyView(BaseModel):
    options: list[JourneyOption]
    sim_time: Timestamp


class ObservedValue(BaseModel):
    value: int | None
    kind: Literal["observed"]
    measured_at: Timestamp | None
    source: Literal["simulated", "physical"] | None
    status: Literal["ok", "stale", "missing"]


class StopView(BaseModel):
    stop_id: str
    name: str
    lat: float
    lon: float
    waiting: ObservedValue
    camera: dict
    next_buses: list[JourneyOption] = []
