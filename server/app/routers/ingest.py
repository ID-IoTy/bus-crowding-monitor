"""Ingestion endpoints called by the Arduino bus & stop devices."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.middleware.auth import require_api_key
from app.models.events import BusEvent, StopEvent
from app.schemas.ingest import BusEventIn, IngestAck, StopEventIn
from app.services import anomaly_detector, correlator
from app.services.utils import utcnow

router = APIRouter(prefix="/ingest", tags=["ingest"], dependencies=[Depends(require_api_key)])


@router.post("/bus-event", response_model=IngestAck)
def ingest_bus_event(payload: BusEventIn, db: Session = Depends(get_db)) -> IngestAck:
    event = BusEvent(
        bus_id=payload.bus_id,
        route_id=payload.route_id,
        stop_id=payload.stop_id,
        timestamp=payload.timestamp or utcnow(),
        passengers_onboard=payload.passengers_onboard,
        door_status=payload.door_status,
        speed_kmh=payload.speed_kmh,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    correlated = correlator.correlate_for_bus_event(db, event)
    message = None
    if correlated is not None:
        anomaly = anomaly_detector.check_overcrowding(db, correlated)
        if anomaly is not None:
            message = f"anomaly:{anomaly.anomaly_type}"

    return IngestAck(
        stored_id=event.id,
        correlated=correlated is not None,
        message=message,
    )


@router.post("/stop-event", response_model=IngestAck)
def ingest_stop_event(payload: StopEventIn, db: Session = Depends(get_db)) -> IngestAck:
    event = StopEvent(
        stop_id=payload.stop_id,
        timestamp=payload.timestamp or utcnow(),
        people_waiting=payload.people_waiting,
        event_type=payload.event_type,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    messages = []

    # A post_departure event completes the picture, so try to correlate now.
    correlated = correlator.correlate_for_stop_event(db, event)
    if correlated is not None:
        anomaly = anomaly_detector.check_overcrowding(db, correlated)
        if anomaly is not None:
            messages.append(f"anomaly:{anomaly.anomaly_type}")

    abnormal = anomaly_detector.check_abnormal_crowd(db, event)
    if abnormal is not None:
        messages.append(f"anomaly:{abnormal.anomaly_type}")
    abandonment = anomaly_detector.check_abandonment(db, event)
    if abandonment is not None:
        messages.append(f"anomaly:{abandonment.anomaly_type}")

    return IngestAck(
        stored_id=event.id,
        correlated=correlated is not None,
        message=", ".join(messages) if messages else None,
    )
