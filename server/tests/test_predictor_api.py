"""Prediction engine and public output API."""
from __future__ import annotations

from app.services.predictor import forecast_remaining_route
from app.services.utils import crowd_label
from tests.helpers import build_small_network


def test_crowd_labels():
    assert crowd_label(0.2) == "LOW"
    assert crowd_label(0.5) == "MEDIUM"
    assert crowd_label(0.75) == "HIGH"
    assert crowd_label(0.95) == "FULL"
    assert crowd_label(1.0) == "FULL"


def test_forecast_in_range_and_blends(client, auth, db_session):
    build_small_network(db_session)
    # Place bus mid-route with 30 aboard (left stop seq 1).
    client.post("/ingest/bus-event", headers=auth, json={
        "bus_id": "BUS-T", "route_id": "RT", "stop_id": "RT-S01",
        "passengers_onboard": 30,
    })
    # People waiting ahead at S03.
    client.post("/ingest/stop-event", headers=auth, json={
        "stop_id": "RT-S03", "people_waiting": 10, "event_type": "periodic",
    })
    forecasts = forecast_remaining_route(db_session, "BUS-T", 30, 1)
    assert forecasts, "expected forecasts for upcoming stops"
    for f in forecasts:
        assert 0.0 <= f.occupancy_on_arrival <= 1.0
        assert 0.0 <= f.occupancy_on_departure <= 1.0
        # Departure never below arrival (people only board, never un-board here).
        assert f.occupancy_on_departure >= f.occupancy_on_arrival - 1e-9


def test_stop_status_endpoint(client, auth, db_session):
    build_small_network(db_session)
    client.post("/ingest/bus-event", headers=auth, json={
        "bus_id": "BUS-T", "route_id": "RT", "stop_id": "RT-S00",
        "passengers_onboard": 20,
    })
    client.post("/ingest/stop-event", headers=auth, json={
        "stop_id": "RT-S03", "people_waiting": 5, "event_type": "periodic",
    })
    r = client.get("/stops/RT-S03/status", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["stop_id"] == "RT-S03"
    assert body["next_buses"], "bus should be reported as upcoming"
    nb = body["next_buses"][0]
    assert 0 <= nb["predicted_occupancy_on_arrival_pct"] <= 100
    assert nb["seats_available_on_arrival"] >= 0


def test_unknown_stop_404(client, auth, db_session):
    build_small_network(db_session)
    assert client.get("/stops/NOPE/status", headers=auth).status_code == 404
