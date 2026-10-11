"""Ingestion storage and event correlation math."""
from __future__ import annotations

from app.models.events import CorrelatedEvent
from tests.helpers import build_small_network


def test_bus_event_stored(client, auth, db_session):
    build_small_network(db_session)
    r = client.post("/ingest/bus-event", headers=auth, json={
        "bus_id": "BUS-T", "route_id": "RT", "stop_id": "RT-S00",
        "passengers_onboard": 10, "door_status": "closed",
    })
    assert r.status_code == 200
    assert r.json()["stored_id"] > 0


def test_malformed_payload_rejected(client, auth, db_session):
    build_small_network(db_session)
    r = client.post("/ingest/bus-event", headers=auth, json={"bus_id": "BUS-T"})
    assert r.status_code == 422


def test_correlation_computes_boarding(client, auth, db_session):
    build_small_network(db_session)
    # Previous departure establishes occupancy_before = 10.
    client.post("/ingest/bus-event", headers=auth, json={
        "bus_id": "BUS-T", "route_id": "RT", "stop_id": "RT-S00",
        "passengers_onboard": 10,
    })
    # Crowd before boarding at S01.
    client.post("/ingest/stop-event", headers=auth, json={
        "stop_id": "RT-S01", "people_waiting": 9, "event_type": "pre_arrival",
    })
    # Bus leaves S01 with 15 aboard (so +5 net).
    client.post("/ingest/bus-event", headers=auth, json={
        "bus_id": "BUS-T", "route_id": "RT", "stop_id": "RT-S01",
        "passengers_onboard": 15,
    })
    # Crowd left behind. This post_departure event triggers correlation.
    r = client.post("/ingest/stop-event", headers=auth, json={
        "stop_id": "RT-S01", "people_waiting": 4, "event_type": "post_departure",
    })
    assert r.json()["correlated"] is True

    rows = db_session.query(CorrelatedEvent).filter_by(stop_id="RT-S01").all()
    assert rows
    latest = rows[-1]
    assert latest.occupancy_after == 15
    assert latest.people_boarded == 5
    assert latest.dwell_time_seconds > 0
