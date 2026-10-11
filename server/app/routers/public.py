"""Public endpoints consumed by the citizen app and stop displays."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.middleware.auth import require_api_key
from app.models.events import BusEvent, StopEvent
from app.models.route import Bus, Stop
from app.schemas.output import (
    BusRouteForecast,
    NextBus,
    RouteForecastStop,
    StopStatus,
)
from app.services import eta_calculator
from app.services.predictor import StopForecast, forecast_remaining_route
from app.services.utils import crowd_label, pct, seconds_to_hhmm, utcnow

router = APIRouter(tags=["public"], dependencies=[Depends(require_api_key)])


def _latest_bus_event(db: Session, bus_id: str) -> BusEvent | None:
    return db.scalars(
        select(BusEvent).where(BusEvent.bus_id == bus_id).order_by(BusEvent.id.desc()).limit(1)
    ).first()


def _current_sequence(db: Session, bus: Bus, last_event: BusEvent | None) -> int:
    """Sequence index of the stop the bus most recently left (-1 = not started)."""
    if last_event is None:
        return -1
    stop = db.get(Stop, last_event.stop_id)
    return stop.sequence if stop else -1


def _build_route_forecast(forecasts: list[StopForecast]) -> list[RouteForecastStop]:
    return [
        RouteForecastStop(
            stop_id=fc.stop_id,
            stop_name=fc.stop_name,
            predicted_occupancy_pct=pct(fc.occupancy_on_departure),
        )
        for fc in forecasts
    ]


@router.get("/stops/{stop_id}/status", response_model=StopStatus)
def stop_status(stop_id: str, db: Session = Depends(get_db)) -> StopStatus:
    stop = db.get(Stop, stop_id)
    if stop is None:
        raise HTTPException(status_code=404, detail=f"Unknown stop {stop_id}")

    # Current crowd at this stop (latest reading).
    latest_stop_ev = db.scalars(
        select(StopEvent).where(StopEvent.stop_id == stop_id).order_by(StopEvent.id.desc()).limit(1)
    ).first()
    current_waiting = latest_stop_ev.people_waiting if latest_stop_ev else 0

    now = utcnow()
    next_buses: list[NextBus] = []

    # Buses on this route that have not yet passed this stop.
    buses = db.scalars(select(Bus).where(Bus.route_id == stop.route_id)).all()
    for bus in buses:
        last_event = _latest_bus_event(db, bus.id)
        seq = _current_sequence(db, bus, last_event)
        if seq >= stop.sequence:
            continue  # bus already passed this stop

        current_occ = last_event.passengers_onboard if last_event else 0
        forecasts = forecast_remaining_route(db, bus.id, current_occ, seq, now)

        target = next((f for f in forecasts if f.stop_id == stop_id), None)
        if target is None:
            continue

        gtt_s, adj_s = eta_calculator.adjusted_eta_seconds(
            db, bus.id, stop_id, forecasts, seq, now
        )
        if gtt_s is None:
            continue

        delay_min = int(round((adj_s - gtt_s) / 60)) if adj_s is not None else 0
        remaining_from_target = [f for f in forecasts if f.sequence > target.sequence]

        next_buses.append(
            NextBus(
                bus_id=bus.id,
                route_id=bus.route_id,
                gtt_eta=seconds_to_hhmm(gtt_s),
                adjusted_eta=seconds_to_hhmm(adj_s if adj_s is not None else gtt_s),
                eta_delay_minutes=delay_min,
                predicted_occupancy_on_arrival_pct=pct(target.occupancy_on_arrival),
                predicted_occupancy_on_departure_pct=pct(target.occupancy_on_departure),
                crowdedness_on_arrival=crowd_label(target.occupancy_on_arrival),
                crowdedness_on_departure=crowd_label(target.occupancy_on_departure),
                seats_available_on_arrival=max(
                    0, bus.capacity - int(round(target.occupancy_on_arrival * bus.capacity))
                ),
                route_forecast=_build_route_forecast(remaining_from_target),
            )
        )

    next_buses.sort(key=lambda b: b.adjusted_eta)
    return StopStatus(
        stop_id=stop.id,
        stop_name=stop.name,
        current_waiting=current_waiting,
        next_buses=next_buses,
    )


@router.get("/buses/{bus_id}/route-forecast", response_model=BusRouteForecast)
def bus_route_forecast(bus_id: str, db: Session = Depends(get_db)) -> BusRouteForecast:
    bus = db.get(Bus, bus_id)
    if bus is None:
        raise HTTPException(status_code=404, detail=f"Unknown bus {bus_id}")

    last_event = _latest_bus_event(db, bus_id)
    seq = _current_sequence(db, bus, last_event)
    current_occ = last_event.passengers_onboard if last_event else 0

    forecasts = forecast_remaining_route(db, bus_id, current_occ, seq)
    return BusRouteForecast(
        bus_id=bus.id,
        route_id=bus.route_id,
        current_occupancy_pct=pct(current_occ / bus.capacity),
        forecast=_build_route_forecast(forecasts),
    )
