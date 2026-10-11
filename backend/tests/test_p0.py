import ast
import asyncio
from datetime import timedelta
from pathlib import Path
import httpx
import pytest
from pydantic import ValidationError
from app.cli import load_network
from app.config import MODEL, SIM
from app.contracts import CameraObservation, ClockCommand
from app.core.db import Store
from app.core.engine import Core, level, timestamp
from app.sim.world import World, schedule


@pytest.fixture
def runtime(tmp_path):
    network = load_network()
    store = Store(f"sqlite:///{tmp_path / 'core.sqlite'}")
    start = timestamp(SIM["start_time"]).replace(hour=6)
    world = None
    core = Core(network, store, lambda: world.now, lambda r, d: schedule(network, r, d))
    world = World(network, start, core, f"sqlite:///{tmp_path / 'truth.sqlite'}", batch=True)
    return world, core


def test_isolation():
    for file in (Path(__file__).parents[1] / "app/core").glob("*.py"):
        tree = ast.parse(file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("app.sim")
            if isinstance(node, ast.Import):
                assert not any(n.name.startswith("app.sim") for n in node.names)


def test_contracts():
    with pytest.raises(ValidationError):
        ClockCommand(speed=61)
    with pytest.raises(ValidationError):
        CameraObservation(observation_id="o", camera_id="cam-3380", stop_id="3380", source="physical", measured_at="2026-10-12T07:00:00", waiting_count=-1, trigger="periodic")
    assert [level(p) for p in [60, 61, 75, 76, 90, 91]] == ["green", "yellow", "yellow", "orange", "orange", "red"]


def test_world_capacity_deterministic(runtime, tmp_path):
    world, core = runtime
    world.run_until(world.now + timedelta(minutes=30))
    truth = world.truth()
    assert all(v["true_onboard"] <= 70 for v in truth["vehicles"])
    assert truth["counters"]["boarded"] > 0
    assert len(core.visits) > 0
    assert any("post_departure" in v for v in core.visits.values())


def test_idempotency_stale_and_missing(runtime):
    world, core = runtime
    assert core.observation_view("3380")["value"] is None
    event = CameraObservation(observation_id="same", camera_id="cam-3380", stop_id="3380", source="physical", measured_at=world.now, waiting_count=0, trigger="periodic")
    assert core.observation(event) == "accepted"
    assert core.observation(event) == "duplicate"
    assert core.observation_view("3380")["value"] == 0
    world.now += timedelta(seconds=MODEL["stale_s"] + 1)
    assert core.observation_view("3380")["value"] is None


def test_journey_forward_dates_capacity(runtime):
    world, core = runtime
    route = core.routes["33U-0"]
    origin, destination = route["stops"][5]["id"], route["stops"][15]["id"]
    options = core.journey(origin, destination)["options"]
    assert options
    for option in options:
        assert option["destinationIndex"] > option["originIndex"]
        assert len(option["trips"]) == 3
        ids = [t["id"] for t in option["trips"]]
        assert len(set(ids)) == 3
        for trip in option["trips"]:
            assert trip["reliability"] is None
            assert trip["seated_capacity"] is None
            for p in trip["passages"]:
                assert 0 <= p["leaving"] <= 70
                assert p["leaving"] == p["arriving"] - p["alighting"] + p["boarding"] or abs(p["leaving"] - p["arriving"] + p["alighting"] - p["boarding"]) <= 1
    assert not any(o["route"]["id"] == route["id"] for o in core.journey(destination, origin)["options"])
    with pytest.raises(ValueError):
        core.journey(origin, origin)
    future = core.journey(origin, destination, world.now + timedelta(days=2))["options"]
    assert all(t["positionKind"] == "predicted" for o in future for t in o["trips"])


def test_live_count_changes_prediction(runtime):
    world, core = runtime
    route = core.routes["33U-0"]
    run = schedule(core.network, route, world.now.replace(hour=0))[0]
    stop = route["stops"][0]["id"]
    before = core.forecast(route, run)["passages"][0]["leaving"]
    core.observation(CameraObservation(observation_id="live", camera_id="cam-" + stop, stop_id=stop, source="physical", measured_at=world.now, waiting_count=30, trigger="periodic"))
    after = core.forecast(route, run)["passages"][0]["leaving"]
    assert after > before


def test_alert_lifecycle(runtime):
    _, core = runtime
    core._alert("CAPACITY_RISK", "3380", True, {"p_red": .9})
    core.ack("CAPACITY_RISK:3380")
    assert core.alerts["CAPACITY_RISK:3380"]["state"] == "acknowledged"
    core._alert("CAPACITY_RISK", "3380", False, {})
    with pytest.raises(ValueError):
        core.ack("CAPACITY_RISK:3380")


def test_mock_contract():
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location("mock_edge", Path(__file__).parents[2] / "edge/mock_edge.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=module.app), base_url="http://mock") as client:
            assert (await client.post("/mock/count", json={"count": 9})).status_code == 200
            assert (await client.get("/count")).json()["count"] == 9
            assert (await client.post("/mock/count", json={"count": -1})).status_code == 422
            await client.post("/mock/fail", json={"mode": "error"})
            assert (await client.get("/count")).status_code == 503
    asyncio.run(run())


def test_api_commands_and_missing_values(runtime):
    from fastapi.testclient import TestClient
    from app.main import app
    world, core = runtime
    app.state.world, app.state.core = world, core
    client = TestClient(app)
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/stops/3380").json()["waiting"]["value"] is None
    assert client.post("/sim/clock", json={"speed": 10, "paused": True}).json()["paused"]
    assert client.post("/sim/clock", json={"speed": 100}).status_code == 422
    assert client.post("/sim/scenario", json={"name": "rush_hour"}).status_code == 200
    assert client.post("/sim/cameras/cam-3380/mode", json={"mode": "physical"}).status_code == 200
    assert client.get("/api/journey?from=3380&to=3380").status_code == 422
    assert client.get("/api/journey?from=unknown").status_code == 404
    assert client.get("/api/journey?from=3380").status_code == 200


def test_physical_gateway_to_forecast_and_display(runtime):
    world, core = runtime
    world.batch = False
    world.now = timestamp(SIM["start_time"])
    route = core.routes["33U-0"]
    index = next(i for i, s in enumerate(route["stops"]) if s["id"] == "3380")
    run = next(r for r in core.schedule(route, world.now.replace(hour=0)) if 0 <= (timestamp(r["startsAt"]) + timedelta(seconds=route["offsets"][index]) - world.now).total_seconds() <= 600)
    control = {"count": 5, "display": None, "fail": False}
    def handle(request):
        if control["fail"]:
            raise httpx.ReadTimeout("Camera timeout", request=request)
        if request.url.path == "/count":
            return httpx.Response(200, json={"count": control["count"], "measured_at": "2026-10-11T10:00:00+02:00"})
        import json
        control["display"] = json.loads(request.content)
        return httpx.Response(204)
    world.transport = httpx.MockTransport(handle)
    world.modes["cam-3380"] = "physical"
    async def check():
        await world._physical("3380", "periodic", None)
        assert core.observation_view("3380")["source"] == "physical"
        before = core.forecast(route, run)["passages"][index]["leaving"]
        world.now += timedelta(seconds=1)
        control["count"] = 30
        await world._physical("3380", "periodic", None)
        after = core.forecast(route, run)["passages"][index]["leaving"]
        assert after > before
        assert world.truth()["stops"][list(world.stops).index("3380")]["true_waiting"] == 30
        await world._display(core.display_stop("3380"))
        assert control["display"]["stop_id"] == "3380"
        control["fail"] = True
        world.now += timedelta(seconds=MODEL["stale_s"] + 1)
        await world._physical("3380", "periodic", None)
        assert core.observation_view("3380")["value"] is None
    asyncio.run(check())
