"""Seeded event world. Only IngestPort/CameraPort communicate with core."""
import asyncio
import heapq
import json
import math
from datetime import timedelta
import numpy as np
import httpx
from sqlalchemy import create_engine, text
from app.config import SIM, MODEL, SCENARIOS
from app.contracts import VehicleApproach, VehicleDeparture, CameraObservation, CountRequest, EdgeCount


def schedule(network, route, day):
    """Assign one fleet per line greedily across both direction schedules."""
    patterns = sorted([r for r in network["lines"] if r["name"] == route["name"]], key=lambda r: r["direction"])
    departures = [(day + timedelta(hours=hour, seconds=offset), r) for hour in range(SIM["service_start_hour"], SIM["service_end_hour"]) for offset in range(0, 3600, SIM["headway_s"]) for r in patterns]
    fleet, results = [], []
    for starts, pattern in sorted(departures, key=lambda pair: (pair[0], pair[1]["direction"])):
        index = next((i for i, (ready, direction) in enumerate(fleet) if ready <= starts and direction == pattern["direction"]), len(fleet))
        available = starts + timedelta(seconds=pattern["offsets"][-1] + SIM["layover_s"])
        opposite = "1" if pattern["direction"] == "0" else "0"
        if index == len(fleet):
            fleet.append((available, opposite))
        else:
            fleet[index] = (available, opposite)
        if pattern["id"] == route["id"]:
            results.append({"id": f"{route['name']}-{route['direction']}-{starts:%Y%m%d-%H%M}", "lineId": route["id"], "vehicleId": f"bus-{route['name']}-{index + 1:02}", "startsAt": starts.isoformat()})
    return results


class World:
    def __init__(self, network, start, core, truth_url, seed=None, batch=False):
        self.network, self.now, self.core, self.batch = network, start, core, batch
        self.rng = np.random.default_rng(SIM["seed"] if seed is None else seed)
        self.heap, self.sequence = [], 0
        self.speed, self.paused, self.scenario = 1, False, "normal"
        self.scenario_at = start
        self.stops = {s["id"]: s for r in network["lines"] for s in r["stops"]}
        self.queues = {s: {} for s in self.stops}
        self.vehicles = {}
        self.modes = {"cam-" + s: "simulated" for s in self.stops}
        self.inflight, self.tasks = set(), set()
        self.transport = None
        self.daily = {s: self.rng.lognormal(0, SIM["daily_noise_sigma"]) for s in self.stops}
        self.counters = {"boarded": 0, "abandoned": 0, "left_behind_events": 0, "added_by_sync": 0, "removed_by_sync": 0}
        self.truth_db = create_engine(truth_url, connect_args={"check_same_thread": False})
        with self.truth_db.begin() as db:
            db.execute(text("CREATE TABLE IF NOT EXISTS truth (at TEXT PRIMARY KEY, payload TEXT)"))
        core.camera = self
        self.add(start, self._minute)
        for stop in self.stops:
            self.add(start + timedelta(seconds=float(self.rng.uniform(0, SIM["periodic_s"]))), self._periodic, stop)
        self._day(start.replace(hour=0, minute=0, second=0, microsecond=0))

    def add(self, at, action, *args):
        self.sequence += 1
        heapq.heappush(self.heap, (at, self.sequence, action, args))

    def run_until(self, until):
        while self.heap and self.heap[0][0] <= until:
            at, _, fn, args = heapq.heappop(self.heap)
            self.now = at
            fn(*args)
        self.now = until

    def _day(self, day):
        for route in self.network["lines"]:
            for run in schedule(self.network, route, day):
                at = __import__('datetime').datetime.fromisoformat(run["startsAt"])
                if at >= self.now:
                    self.add(at, self._approach, route, run, 0, [], 0)
        self.add(day + timedelta(days=1), self._day, day + timedelta(days=1))

    def hub(self, stop):
        return stop == SIM["physical_stop_id"] or len({r["name"] for r in self.network["lines"] if any(s["id"] == stop for s in r["stops"])}) > 1

    def _minute(self):
        weekend = self.now.weekday() >= 5
        peak = SCENARIOS[self.scenario]["force_peak"] or (not weekend and (7.5 <= self.now.hour + self.now.minute / 60 < 9 or 17 <= self.now.hour < 19))
        for route in self.network["lines"]:
            for index, stop in enumerate(route["stops"][:-1]):
                stop_id = stop["id"]
                queue = self.queues[stop_id].setdefault(route["id"], [])
                before = len(queue)
                queue[:] = [(dest, deadline) for dest, deadline in queue if deadline > self.now]
                self.counters["abandoned"] += before - len(queue)
                rate = SIM["arrival_per_minute"] * self.daily[stop_id] * (SIM["weekend_multiplier"] if weekend else 1)
                if peak:
                    rate *= SIM["peak_hub_multiplier"] if self.hub(stop_id) else SIM["peak_other_multiplier"]
                if stop_id == SIM["physical_stop_id"] and (self.now - self.scenario_at).total_seconds() < SCENARIOS[self.scenario]["target_duration_s"]:
                    rate *= SCENARIOS[self.scenario]["target_multiplier"]
                for _ in range(int(self.rng.poisson(rate))):
                    destination = int(self.rng.integers(index + 1, len(route["stops"])))
                    deadline = self.now + timedelta(seconds=float(self.rng.lognormal(math.log(SIM["patience_median_s"]), SIM["patience_sigma"])))
                    queue.append((destination, deadline))
        if not self.batch:
            with self.truth_db.begin() as db:
                db.execute(text("INSERT OR REPLACE INTO truth VALUES (:at,:payload)"), {"at": self.now.isoformat(), "payload": json.dumps(self.truth())})
        self.add(self.now + timedelta(seconds=60), self._minute)

    def _periodic(self, stop):
        self._read(stop, "periodic", None)
        self.add(self.now + timedelta(seconds=SIM["periodic_s"]), self._periodic, stop)

    def count_request(self, camera_id, request: CountRequest):
        self.add(self.now + timedelta(seconds=request.delay_s), self._read, camera_id.removeprefix("cam-"), request.reason, request)

    def _emit(self, stop, count, source, trigger, request, device=None):
        self.core.observation(CameraObservation(observation_id=f"obs-cam-{stop}-{self.now:%Y%m%dT%H%M%S%f}-{trigger}-{request.request_id if request else 'periodic'}", camera_id="cam-" + stop, stop_id=stop, source=source, measured_at=self.now, waiting_count=count, trigger=trigger, request_id=request.request_id if request else None, visit_id=request.visit_id if request else None, device_measured_at=device))

    def _read(self, stop, trigger, request):
        if self.modes["cam-" + stop] == "physical":
            if stop in self.inflight or self.batch:
                return
            self.inflight.add(stop)
            task = asyncio.create_task(self._physical(stop, trigger, request))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
            return
        waiting = sum(len(q) for q in self.queues[stop].values())
        passersby = int(self.rng.poisson(SIM["passerby_per_minute"] * (SIM["passerby_hub_multiplier"] if self.hub(stop) else 1) * (SIM["passerby_min_s"] + SIM["passerby_max_s"]) / 120))
        n = waiting + passersby
        count = max(0, round(n * (1 + self.rng.normal(0, SIM["camera_error"])) - SIM["camera_occlusion"] * max(0, n - SIM["camera_occlusion_above"])))
        self._emit(stop, count, "simulated", trigger, request)

    async def _physical(self, stop, trigger, request):
        try:
            async with httpx.AsyncClient(timeout=MODEL["edge_timeout_s"], transport=self.transport) as client:
                response = await client.get(SIM["physical_camera_url"] + "/count")
                response.raise_for_status()
                reading = EdgeCount.model_validate(response.json())
            self._sync(stop, reading.count)
            self._emit(stop, reading.count, "physical", trigger, request, reading.measured_at)
        except (httpx.HTTPError, ValueError):
            pass  # No invented reading; core freshness will report sensor unavailable.
        finally:
            self.inflight.discard(stop)

    def _sync(self, stop, count):
        routes = [(r, i) for r in self.network["lines"] for i, s in enumerate(r["stops"][:-1]) if s["id"] == stop]
        current = sum(len(q) for q in self.queues[stop].values())
        while current > count:
            queue = max(self.queues[stop].values(), key=len)
            queue.pop()
            current -= 1
            self.counters["removed_by_sync"] += 1
        while current < count:
            route, index = routes[int(self.rng.integers(len(routes)))]
            self.queues[stop].setdefault(route["id"], []).append((int(self.rng.integers(index + 1, len(route["stops"]))), self.now + timedelta(seconds=SIM["patience_median_s"])))
            current += 1
            self.counters["added_by_sync"] += 1

    def _approach(self, route, run, index, passengers, reported):
        if index == 0:
            previous = self.vehicles.get(run["vehicleId"])
            if previous and previous.get("active"):
                self.add(self.now + timedelta(seconds=SIM["periodic_s"]), self._approach, route, run, index, passengers, reported)
                return
        stop = route["stops"][index]
        at = self.now + timedelta(seconds=SIM["approach_s"] if index else 0)
        trip = run["id"]
        self.core.approach(VehicleApproach(event_id=f"{trip}-s{index}-approach", vehicle_id=run["vehicleId"], trip_id=trip, line_id=route["name"], direction=route["direction"], next_stop_id=stop["id"], stop_sequence=index, eta_s=max(0, int((at - self.now).total_seconds())), lat=stop["lat"], lon=stop["lon"], onboard=reported, sim_time=self.now))
        self.add(at, self._arrive, route, run, index, passengers, reported)

    def _arrive(self, route, run, index, passengers, reported):
        alighted = sum(dest == index for dest in passengers)
        passengers = [dest for dest in passengers if dest != index]
        stop = route["stops"][index]
        queue = self.queues[stop["id"]].setdefault(route["id"], [])
        boarded = min(len(queue), SIM["capacity"] - len(passengers)) if index < len(route["stops"]) - 1 else 0
        passengers.extend(dest for dest, _ in queue[:boarded])
        del queue[:boarded]
        self.counters["boarded"] += boarded
        self.counters["left_behind_events"] += len(queue)
        self.vehicles[run["vehicleId"]] = {"trip_id": run["id"], "true_onboard": len(passengers), "stop_id": stop["id"], "active": True}
        if index == len(route["stops"]) - 1:
            passengers = []
        reported_boarded = max(0, round(boarded * (1 + self.rng.normal(0, SIM["apc_error"]))))
        reported_off = max(0, round(alighted * (1 + self.rng.normal(0, SIM["apc_error"]))))
        onboard = max(0, reported + reported_boarded - reported_off + int(self.rng.random() < SIM["apc_drift_probability"]))
        dwell = SIM["dwell_base_s"] + SIM["boarding_s"] * boarded + SIM["alighting_s"] * alighted
        self.add(self.now + timedelta(seconds=dwell), self._depart, route, run, index, passengers, onboard, reported_boarded, reported_off, self.now)

    def _depart(self, route, run, index, passengers, reported, boarded, alighted, arrived):
        stop = route["stops"][index]
        terminal = index == len(route["stops"]) - 1
        if terminal:
            self.vehicles[run["vehicleId"]]["active"] = False
        self.core.departure(VehicleDeparture(event_id=f"{run['id']}-s{index}-departure", vehicle_id=run["vehicleId"], trip_id=run["id"], line_id=route["name"], direction=route["direction"], stop_id=stop["id"], stop_sequence=index, arrived_at=arrived, doors_closed_at=self.now, boarded=boarded, alighted=alighted, onboard=reported, lat=stop["lat"], lon=stop["lon"], is_terminus=terminal))
        if not terminal:
            travel = max(SIM["approach_s"], (route["offsets"][index + 1] - route["offsets"][index] - (self.now - arrived).total_seconds()) * float(self.rng.lognormal(0, SIM["travel_noise_sigma"])))
            self.add(self.now + timedelta(seconds=max(0, travel - SIM["approach_s"])), self._approach, route, run, index + 1, passengers, reported)

    def display(self, camera_id, payload):
        if self.modes[camera_id] == "physical" and not self.batch:
            task = asyncio.create_task(self._display(payload))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)

    async def _display(self, payload):
        try:
            async with httpx.AsyncClient(timeout=MODEL["edge_timeout_s"], transport=self.transport) as client:
                await client.post(SIM["physical_camera_url"] + "/display", json=payload.model_dump(mode="json"))
        except httpx.HTTPError:
            pass

    def state(self):
        return {"sim_time": self.now.isoformat(), "speed": self.speed, "paused": self.paused, "scenario": self.scenario, "cameras": [{"camera_id": k, "mode": v} for k, v in self.modes.items()]}

    def truth(self):
        return {"sim_time": self.now.isoformat(), "kind": "simulated", "stops": [{"stop_id": s, "true_waiting": sum(len(q) for q in queues.values()), "true_waiting_by_line": {r: len(q) for r, q in queues.items()}} for s, queues in self.queues.items()], "vehicles": list(self.vehicles.values()), "counters": self.counters.copy()}
