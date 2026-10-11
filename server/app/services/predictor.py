"""Crowdedness prediction engine.

Two layers, as described in the README:

1. A trained ML model (GradientBoostingRegressor) when scikit-learn + a saved
   model are available.
2. A deterministic rule-based estimator used as a fallback whenever the ML
   model is missing. This guarantees the demo always works.

Both layers predict, for every upcoming stop on a bus's route, the occupancy
(as a fraction of capacity) ON ARRIVAL (before boarding) and ON DEPARTURE
(after the waiting crowd boards).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BUS_CAPACITY, MODEL_PATH
from app.models.events import CorrelatedEvent, StopEvent
from app.models.route import Bus, Stop
from app.services.utils import utcnow

# --------------------------------------------------------------------------- #
# Optional ML model loading
# --------------------------------------------------------------------------- #
_model = None
_model_tried = False


def _load_model():
    global _model, _model_tried
    if _model_tried:
        return _model
    _model_tried = True
    try:
        import joblib  # type: ignore

        if MODEL_PATH.exists():
            _model = joblib.load(MODEL_PATH)
    except Exception:  # pragma: no cover - defensive, ML stack optional
        _model = None
    return _model


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #
@dataclass
class StopForecast:
    stop_id: str
    stop_name: str
    sequence: int
    occupancy_on_arrival: float   # fraction 0..1
    occupancy_on_departure: float  # fraction 0..1


# --------------------------------------------------------------------------- #
# Historical helpers
# --------------------------------------------------------------------------- #
def _avg_boarding_at_stop(db: Session, stop_id: str, hour: int) -> float:
    """Average historical boardings at a stop around a given hour of day."""
    rows = db.scalars(
        select(CorrelatedEvent).where(CorrelatedEvent.stop_id == stop_id)
    ).all()
    if not rows:
        return 3.0  # sensible default when we have no history yet
    same_hour = [r.people_boarded for r in rows if r.timestamp.hour == hour]
    sample = same_hour or [r.people_boarded for r in rows]
    return sum(sample) / len(sample)


def _alighting_rate_at_stop(db: Session, stop_id: str) -> float:
    """Historical FRACTION of onboard passengers who get off at this stop.

    Returned as a rate in 0..0.9 so it scales with the live occupancy instead
    of being a fixed absolute count (which would wrongly empty a full bus).
    """
    rows = db.scalars(
        select(CorrelatedEvent).where(CorrelatedEvent.stop_id == stop_id)
    ).all()
    if not rows:
        return 0.1
    rates = []
    for r in rows:
        if r.occupancy_before > 0:
            rates.append(r.people_alighted / r.occupancy_before)
    if not rates:
        return 0.1
    return min(0.9, sum(rates) / len(rates))


def _current_waiting(db: Session, stop_id: str) -> int | None:
    """Most recent reported waiting count at a stop, if any."""
    ev = db.scalars(
        select(StopEvent).where(StopEvent.stop_id == stop_id).order_by(StopEvent.id.desc()).limit(1)
    ).first()
    return ev.people_waiting if ev else None


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def forecast_remaining_route(
    db: Session,
    bus_id: str,
    current_occupancy: int,
    current_sequence: int,
    now: datetime | None = None,
) -> list[StopForecast]:
    """Predict occupancy at every stop AFTER current_sequence on the bus's route."""
    now = now or utcnow()
    bus = db.get(Bus, bus_id)
    if bus is None:
        return []

    upcoming = db.scalars(
        select(Stop)
        .where(Stop.route_id == bus.route_id, Stop.sequence > current_sequence)
        .order_by(Stop.sequence)
    ).all()

    model = _load_model()
    forecasts: list[StopForecast] = []
    occupancy = float(current_occupancy)

    for stop in upcoming:
        avg_board = _avg_boarding_at_stop(db, stop.id, now.hour)
        alight_rate = _alighting_rate_at_stop(db, stop.id)
        waiting_now = _current_waiting(db, stop.id)

        # Alighting scales with how full the bus currently is.
        occ_arrival = max(0.0, occupancy * (1.0 - alight_rate))

        if model is not None:
            boarders = _predict_boarders_ml(
                model, occ_arrival, stop.sequence, now, avg_board, waiting_now
            )
        else:
            boarders = _predict_boarders_rules(avg_board, waiting_now)

        free_seats = max(0.0, BUS_CAPACITY - occ_arrival)
        actual_boarders = min(boarders, free_seats)
        occ_departure = min(float(BUS_CAPACITY), occ_arrival + actual_boarders)

        forecasts.append(
            StopForecast(
                stop_id=stop.id,
                stop_name=stop.name,
                sequence=stop.sequence,
                occupancy_on_arrival=occ_arrival / BUS_CAPACITY,
                occupancy_on_departure=occ_departure / BUS_CAPACITY,
            )
        )
        occupancy = occ_departure  # carry forward to the next stop

    return forecasts


def _predict_boarders_rules(avg_board: float, waiting_now: int | None) -> float:
    """Rule-based estimate: blend live waiting count with historical average."""
    if waiting_now is not None:
        # Trust the live camera more, but temper it with history.
        return 0.7 * waiting_now + 0.3 * avg_board
    return avg_board


def _predict_boarders_ml(model, occ_arrival, sequence, now, avg_board, waiting_now) -> float:
    """ML estimate. Falls back to rules if the feature vector fails."""
    try:
        features = [[
            occ_arrival / BUS_CAPACITY,
            sequence,
            now.hour,
            now.weekday(),
            avg_board,
            waiting_now if waiting_now is not None else avg_board,
        ]]
        pred = float(model.predict(features)[0])
        return max(0.0, pred)
    except Exception:
        return _predict_boarders_rules(avg_board, waiting_now)
