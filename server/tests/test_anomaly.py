"""Anomaly detection rules."""
from __future__ import annotations

from app.models.anomaly import AnomalyQueue
from tests.helpers import build_small_network


def _overcrowd(client, auth):
    # occupancy_before 60 -> leaves at 72 (96%) with 8 still waiting
    client.post("/ingest/bus-event", headers=auth, json={
        "bus_id": "BUS-T", "route_id": "RT", "stop_id": "RT-S00",
        "passengers_onboard": 60,
    })
    client.post("/ingest/stop-event", headers=auth, json={
        "stop_id": "RT-S01", "people_waiting": 20, "event_type": "pre_arrival",
    })
    client.post("/ingest/bus-event", headers=auth, json={
        "bus_id": "BUS-T", "route_id": "RT", "stop_id": "RT-S01",
        "passengers_onboard": 72,
    })
    # post_departure triggers correlation + overcrowding check.
    return client.post("/ingest/stop-event", headers=auth, json={
        "stop_id": "RT-S01", "people_waiting": 8, "event_type": "post_departure",
    })


def test_overcrowding_detected(client, auth, admin_auth, db_session):
    build_small_network(db_session)
    r = _overcrowd(client, auth)
    assert "OVERCROWDING" in (r.json().get("message") or "")

    rows = db_session.query(AnomalyQueue).filter_by(anomaly_type="OVERCROWDING").all()
    assert rows and rows[0].severity == "HIGH"
    assert rows[0].status == "PENDING"


def test_anomaly_appears_in_admin_queue(client, auth, admin_auth, db_session):
    build_small_network(db_session)
    _overcrowd(client, auth)
    data = client.get("/admin/anomalies?status=PENDING", headers=admin_auth).json()
    assert data["total"] >= 1
    assert data["anomalies"][0]["anomaly_type"] == "OVERCROWDING"
