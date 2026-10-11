"""Import all models so SQLAlchemy's metadata knows about every table."""
from app.models.anomaly import AnomalyQueue
from app.models.events import BusEvent, CorrelatedEvent, StopEvent
from app.models.predictions import Prediction
from app.models.route import Bus, Route, Schedule, Stop

__all__ = [
    "AnomalyQueue",
    "BusEvent",
    "CorrelatedEvent",
    "StopEvent",
    "Prediction",
    "Bus",
    "Route",
    "Schedule",
    "Stop",
]
