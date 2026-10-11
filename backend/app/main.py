"""One localhost process wires contracts, simulator, core and the camera gateway."""
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import time
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.cli import load_network
from app.config import ROOT, SIM, MODEL, SCENARIOS
from app.contracts import VehicleApproach, VehicleDeparture, CameraObservation, ClockCommand, ScenarioCommand, CameraModeCommand, WsEnvelope
from app.contracts.views import JourneyView, StopView
from app.contracts.history import HistoryView
from app.core.history import history_view
from datetime import date
from app.core.db import Store
from app.core.engine import Core, timestamp
from app.sim.world import World, schedule


def build_runtime(db_url=None, truth_url=None):
    network = load_network()
    store = Store(db_url or f"sqlite:///{ROOT / 'backend/server.sqlite'}")
    store.clear_live()
    world = None
    core = Core(network, store, lambda: world.now, lambda r, d: schedule(network, r, d))
    start = timestamp(SIM["start_time"])
    world = World(network, start.replace(hour=SIM["service_start_hour"], minute=0), core, truth_url or f"sqlite:///{ROOT / 'backend/sim.sqlite'}")
    with store.engine.begin() as connection:
        store.bulk = connection
        world.run_until(start)
    store.bulk = None
    return world, core


@asynccontextmanager
async def lifespan(app):
    world, core = build_runtime()
    app.state.world, app.state.core = world, core
    async def tick():
        last = time.monotonic()
        refresh_at = world.now
        while True:
            await asyncio.sleep(.1)
            current = time.monotonic()
            if not world.paused:
                world.run_until(world.now + timedelta(seconds=(current - last) * world.speed))
            last = current
            if core.dirty and world.now >= refresh_at:
                core.refresh()
                refresh_at = world.now + timedelta(seconds=MODEL["recompute_s"])
                camera = "cam-" + SIM["physical_stop_id"]
                world.display(camera, core.display_stop(SIM["physical_stop_id"]))
    task = asyncio.create_task(tick())
    yield
    task.cancel()
    for pending in world.tasks:
        pending.cancel()
    await asyncio.gather(task, *world.tasks, return_exceptions=True)


app = FastAPI(title="Bus Crowding Monitor P0", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (5173, 5174)], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


def runtime():
    return app.state.world, app.state.core


@app.get("/api/health")
def health():
    world, core = runtime()
    return {"status": "ok", "sim_time": world.now.isoformat(), "model_version": "p0-averages", "trained": bool(core.stats)}


@app.get("/api/lines")
def lines():
    return runtime()[1].network


@app.get("/api/stops", response_model=list[StopView])
def stops():
    world, core = runtime()
    return [{"stop_id": s["id"], "name": s["name"], "lat": s["lat"], "lon": s["lon"], "waiting": core.observation_view(s["id"]), "camera": {"camera_id": "cam-" + s["id"], "mode": world.modes["cam-" + s["id"]]}, "next_buses": []} for s in core.stops.values()]


@app.get("/api/lines/{line_id}")
def line(line_id: str):
    core = runtime()[1]
    if line_id not in core.routes:
        raise HTTPException(404, "Unknown route pattern")
    return core.routes[line_id]


@app.get("/api/stops/{stop_id}", response_model=StopView)
def stop(stop_id: str):
    world, core = runtime()
    if stop_id not in core.stops:
        raise HTTPException(404, "Unknown stop")
    s = core.stops[stop_id]
    return {"stop_id": stop_id, "name": s["name"], "lat": s["lat"], "lon": s["lon"], "waiting": core.observation_view(stop_id), "camera": {"mode": world.modes["cam-" + stop_id]}, "next_buses": core.journey(stop_id)["options"]}


@app.get("/api/vehicles")
def vehicles():
    core = runtime()[1]
    return [{"vehicle_id": key, **value, "kind": "observed", "source": "simulated", "status": "stale" if (core.now() - timestamp(value["at"])).total_seconds() > MODEL["stale_s"] else "ok"} for key, value in core.vehicles.items()]


@app.get("/api/vehicles/{vehicle_id}")
def vehicle(vehicle_id: str):
    core = runtime()[1]
    if vehicle_id not in core.vehicles:
        raise HTTPException(404, "Unknown vehicle")
    item = core.vehicles[vehicle_id]
    route = core.routes[item["route"]]
    day = core.now().replace(hour=0, minute=0, second=0, microsecond=0)
    run = next((r for r in core.schedule(route, day) if r["id"] == item["event"]["trip_id"]), None)
    return {"observation": item, "forecast": core.forecast(route, run) if run else None}


@app.get("/api/journey", response_model=JourneyView)
def journey(origin: str = Query(alias="from"), destination: str = Query(default="", alias="to"), requested_at: str | None = None):
    core = runtime()[1]
    try:
        requested = timestamp(requested_at) if requested_at else core.now()
        if requested < core.now() - timedelta(seconds=1):
            raise ValueError("Choose a future time or Now")
        return core.journey(origin, destination, requested)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/operator/history", response_model=HistoryView)
def operator_history(start: date | None = None, end: date | None = None,
                     route_id: str | None = None, stop_id: str | None = None):
    try:
        return history_view(runtime()[1], SIM["capacity"], MODEL["color_thresholds"][-1] * 100,
                            start, end, route_id, stop_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/operator/alerts")
def alerts():
    return list(runtime()[1].alerts.values())


@app.post("/api/operator/alerts/{alert_id:path}/ack")
def acknowledge(alert_id: str):
    try:
        return runtime()[1].ack(alert_id)
    except KeyError as exc:
        raise HTTPException(404, "Unknown alert") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/sim/state")
def state():
    return runtime()[0].state()


@app.post("/sim/clock")
def clock(command: ClockCommand):
    world = runtime()[0]
    if command.speed is not None:
        world.speed = command.speed
    if command.paused is not None:
        world.paused = command.paused
    return world.state()


@app.get("/sim/scenarios")
def scenarios():
    return list(SCENARIOS)


@app.post("/sim/scenario")
def scenario(command: ScenarioCommand):
    world = runtime()[0]
    world.scenario, world.scenario_at = command.name, world.now
    return world.state()


@app.get("/sim/cameras")
def cameras():
    return state()["cameras"]


@app.post("/sim/cameras/{camera_id}/mode")
def mode(camera_id: str, command: CameraModeCommand):
    world = runtime()[0]
    if camera_id not in world.modes:
        raise HTTPException(404, "Unknown camera")
    if command.mode == "physical" and camera_id != "cam-" + SIM["physical_stop_id"]:
        raise HTTPException(409, "No physical device configured for this camera")
    world.modes[camera_id] = command.mode
    return world.state()


@app.get("/sim/truth")
def truth():
    return runtime()[0].truth()


@app.post("/ingest/vehicle/approach")
def approach(event: VehicleApproach):
    return {"duplicate": runtime()[1].approach(event) == "duplicate"}


@app.post("/ingest/vehicle/departure")
def departure(event: VehicleDeparture):
    return {"duplicate": runtime()[1].departure(event) == "duplicate"}


@app.post("/ingest/camera/observation")
def observation(event: CameraObservation):
    try:
        return {"duplicate": runtime()[1].observation(event) == "duplicate"}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/ws-schema", response_model=WsEnvelope)
def schema():
    return WsEnvelope(type="clock", sim_time=runtime()[0].now, data=state())


@app.websocket("/ws/live")
async def websocket(ws: WebSocket):
    if ws.headers.get("origin") not in [f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (5173, 5174)]:
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        while True:
            for kind, value in (("clock", state()), ("vehicles", vehicles()), ("stops", stops()), ("alerts", alerts())):
                await ws.send_json({"type": kind, "sim_time": state()["sim_time"], "data": value})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
