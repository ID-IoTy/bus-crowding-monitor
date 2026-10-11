from datetime import date
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from app.cli import load_network
from app.core.db import Store
from app.core.engine import Core, timestamp
from app.core.history import history_view


@pytest.fixture
def archive(tmp_path):
    network = load_network()
    core = Core(network, Store(f"sqlite:///{tmp_path / 'history.sqlite'}"),
                lambda: timestamp("2026-10-12T07:00:00+02:00"), lambda *_: [])
    route = next(r for r in network["lines"] if any(s["id"] == "3380" for s in r["stops"]))
    for i, count in enumerate((2, 4)):
        core.store.append(f"w{i}", "observation", "history", {
            "stop_id": "3380", "waiting_count": count, "trigger": "periodic",
            "measured_at": f"2026-10-05T0{7+i}:00:00+02:00"})
        core.store.append(f"v{i}", "departure", "history", {
            "stop_id": "3380", "onboard": (14, 70)[i], "line_id": route["name"],
            "direction": route["direction"], "doors_closed_at": f"2026-10-05T0{7+i}:00:00+02:00"})
    # Around-visit samples and live observations must not bias historical averages.
    core.store.append("visit", "observation", "history", {"stop_id": "3380", "waiting_count": 50,
        "trigger": "pre_arrival", "measured_at": "2026-10-05T07:00:00+02:00"})
    core.store.append("live", "observation", "live", {"stop_id": "3380", "waiting_count": 100,
        "trigger": "periodic", "measured_at": "2026-10-12T07:00:00+02:00"})
    return core, route


def test_historical_averages_and_missing_hours(archive):
    core, _ = archive
    result = history_view(core, 70, 90)
    assert result.summary.waiting_mean == 3
    assert result.summary.onboard_percent_mean == 60
    assert result.summary.high_load_percent == 50
    assert result.summary.waiting_samples == 2
    assert result.summary.observed_stops == 1
    assert result.available_from == date(2026, 10, 5)
    assert result.hourly[6].waiting_mean is None
    assert result.hourly[7].waiting_mean == 2
    assert result.busiest_stops[0].peak_waiting == 4


def test_filters_and_shared_counts(archive):
    core, route = archive
    result = history_view(core, 70, 90, route_id=route["id"], stop_id="3380")
    assert result.summary.vehicle_samples == 2
    other = next(r for r in core.routes.values() if r["id"] != route["id"] and any(s["id"] == "3380" for s in r["stops"]))
    result = history_view(core, 70, 90, route_id=other["id"], stop_id="3380")
    assert result.summary.waiting_samples == 2
    assert result.summary.vehicle_samples == 0
    assert result.summary.onboard_percent_mean is None
    outside = history_view(core, 70, 90, date(2026, 11, 1), date(2026, 11, 2))
    assert outside.summary.waiting_mean is None
    assert outside.daily == []


def test_empty_archive_and_invalid_filters(tmp_path):
    core = Core(load_network(), Store(f"sqlite:///{tmp_path / 'empty.sqlite'}"),
                lambda: timestamp("2026-10-12T07:00:00+02:00"), lambda *_: [])
    assert history_view(core, 70, 90).available_from is None
    with pytest.raises(ValueError):
        history_view(core, 70, 90, date(2026, 10, 10), date(2026, 10, 1))
    with pytest.raises(LookupError):
        history_view(core, 70, 90, route_id="unknown")


def test_history_api_contract(archive):
    from app.main import app
    core, _ = archive
    app.state.world = SimpleNamespace(now=core.now())
    app.state.core = core
    client = TestClient(app)
    response = client.get("/api/operator/history", params={"stop_id": "3380"})
    assert response.status_code == 200
    assert response.json()["source"] == "synthetic_history"
    assert response.json()["summary"]["waiting_mean"] == 3
    assert client.get("/api/operator/history?start=bad").status_code == 422
    assert client.get("/api/operator/history?stop_id=unknown").status_code == 404
    assert client.get("/api/operator/history?start=2026-10-20&end=2026-10-01").status_code == 422
