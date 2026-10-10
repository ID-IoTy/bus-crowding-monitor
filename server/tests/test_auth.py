"""Authentication behaviour."""
from __future__ import annotations


def test_health_needs_no_key(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ingest_requires_key(client):
    r = client.post("/ingest/stop-event", json={
        "stop_id": "RT-S00", "people_waiting": 3, "event_type": "periodic"
    })
    assert r.status_code == 401


def test_admin_rejects_normal_key(client, auth):
    r = client.get("/admin/anomalies", headers=auth)
    assert r.status_code == 401


def test_admin_accepts_admin_key(client, admin_auth):
    r = client.get("/admin/anomalies", headers=admin_auth)
    assert r.status_code == 200
