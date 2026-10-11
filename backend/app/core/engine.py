"""Ingestion, visit correlation and history/live Monte Carlo forecasts.

No simulator imports or truth-database access. The schedule and clock are injected.
"""
import hashlib
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import numpy as np
from app.config import MODEL, SIM
from app.contracts import CameraObservation, CountRequest, VehicleApproach, VehicleDeparture, DisplayBus, DisplayPayload
from app.core.utils import pct, crowd_label

ROME = ZoneInfo("Europe/Rome")


def timestamp(value):
    return datetime.fromisoformat(value).astimezone(ROME)


def level(percent):
    return crowd_label(percent / 100)


class Core:
    def __init__(self, network, store, now, schedule, dataset="live"):
        self.network, self.store, self.now, self.schedule = network, store, now, schedule
        self.dataset = dataset
        self.camera = None
        self.stops = {s["id"]: s for r in network["lines"] for s in r["stops"]}
        self.routes = {r["id"]: r for r in network["lines"]}
        self.observations, self.vehicles, self.visits, self.last_departures = {}, {}, {}, {}
        self.alerts = {}
        self.stats = store.stats()
        self.dirty = True
        self.geometry = {}
        for route in network["lines"]:
            points = route["shape"]
            cursor, anchors = 0, []
            for stop in route["stops"]:
                cursor = min(range(cursor, len(points)), key=lambda i: (points[i][0] - stop["lat"]) ** 2 + (points[i][1] - stop["lon"]) ** 2)
                anchors.append(cursor)
            self.geometry[route["id"]] = (points, anchors)

    def _save(self, event, kind, key):
        payload = event.model_dump(mode="json")
        payload["received_at"] = self.now().isoformat()
        if not self.store.append(key, kind, self.dataset, payload):
            return False
        self.dirty = True
        return True

    def approach(self, event: VehicleApproach):
        route = self._route(event.line_id, event.direction)
        if event.next_stop_id not in self.stops or route["stops"][event.stop_sequence]["id"] != event.next_stop_id:
            raise ValueError("Unknown route stop")
        if not self._save(event, "approach", event.event_id):
            return "duplicate"
        self.vehicles[event.vehicle_id] = {"event": event.model_dump(mode="json"), "at": event.sim_time.isoformat(), "route": route["id"], "index": event.stop_sequence, "onboard": event.onboard}
        visit = f"visit-{event.trip_id}-s{event.stop_sequence}"
        self.visits.setdefault(visit, {})["approach"] = event
        if self.camera:
            self.camera.count_request("cam-" + event.next_stop_id, CountRequest(request_id="req-" + hashlib.sha256(visit.encode()).hexdigest()[:8], visit_id=visit, reason="pre_arrival"))
        return "accepted"

    def _route(self, line, direction):
        return next(r for r in self.network["lines"] if r["name"] == line and r["direction"] == direction)

    def departure(self, event: VehicleDeparture):
        route = self._route(event.line_id, event.direction)
        if route["stops"][event.stop_sequence]["id"] != event.stop_id:
            raise ValueError("Unknown route stop")
        if not self._save(event, "departure", event.event_id):
            return "duplicate"
        self.vehicles[event.vehicle_id] = {"event": event.model_dump(mode="json"), "at": event.doors_closed_at.isoformat(), "route": route["id"], "index": event.stop_sequence, "onboard": 0 if event.is_terminus else event.onboard}
        visit = f"visit-{event.trip_id}-s{event.stop_sequence}"
        self.visits.setdefault(visit, {})["departure"] = event
        self.last_departures[(route["id"], event.stop_id)] = event.doors_closed_at
        if self.camera:
            self.camera.count_request("cam-" + event.stop_id, CountRequest(request_id="req-" + hashlib.sha256((visit + "post").encode()).hexdigest()[:8], visit_id=visit, reason="post_departure", delay_s=MODEL["post_departure_s"]))
        return "accepted"

    def observation(self, event: CameraObservation):
        if event.stop_id not in self.stops:
            raise ValueError("Unknown stop")
        if not self._save(event, "observation", event.observation_id):
            return "duplicate"
        latest = self.observations.get(event.stop_id)
        if latest is None or event.measured_at >= latest.measured_at:
            self.observations[event.stop_id] = event
        self._alert("SENSOR_STALE", event.stop_id, False, {"observation_id": event.observation_id})
        if event.visit_id:
            visit = self.visits.setdefault(event.visit_id, {})
            visit[event.trigger] = event
            if event.trigger == "post_departure" and "departure" in visit:
                dep = visit["departure"]
                stat = self._stat(self._route(dep.line_id, dep.direction), dep.stop_id, event.measured_at)
                full = dep.onboard >= MODEL["departed_full_ratio"] * SIM["capacity"]
                pre = visit.get("pre_arrival")
                valid = pre and abs((dep.arrived_at - pre.measured_at).total_seconds()) <= MODEL["stale_s"]
                residual = max(0, event.waiting_count - stat["passersby"] - stat["rate"] * MODEL["post_departure_s"])
                if valid:
                    residual = max(0, residual - (1 - stat["share"]) * max(0, pre.waiting_count - stat["passersby"]))
                self._alert("LEFT_BEHIND", event.stop_id + ":" + dep.line_id, bool(full and valid and residual > MODEL["left_behind_threshold"]), {"visit_id": event.visit_id, "residual_estimate": residual if valid else None, "kind": "predicted", "source": event.source})
        profile = self.stats.get("waiting:" + self._bucket(event.stop_id, event.measured_at))
        if profile:
            z = (event.waiting_count - profile["mean"]) / math.sqrt(max(MODEL["crowd_variance_floor"], profile["var"]))
            key = "CROWD_ANOMALY:" + event.stop_id
            close = z < MODEL["crowd_z_close"]
            if close:
                previous = self.alerts.get(key, {})
                previous["clear_count"] = previous.get("clear_count", 0) + 1
            self._alert("CROWD_ANOMALY", event.stop_id, z > MODEL["crowd_z_open"] or (key in self.alerts and not (close and self.alerts[key].get("clear_count", 0) >= 2)), {"z_score": z, "observation_id": event.observation_id})
        return "accepted"

    def _bucket(self, stop, at):
        return f"{stop}:{at.hour}:{'weekend' if at.weekday() >= 5 else 'weekday'}"

    def _stat(self, route, stop, at):
        key = route["id"] + ":" + self._bucket(stop, at)
        n = len({r["id"] for r in self.network["lines"] if any(s["id"] == stop for s in r["stops"][:-1])})
        return self.stats.get(key, {"rate": SIM["arrival_per_minute"] / 60, "alpha": .15, "share": 1 / max(1, n), "share_var": MODEL["share_prior_variance"] if n > 1 else 0, "passersby": SIM["passerby_per_minute"] / 60 * (SIM["passerby_min_s"] + SIM["passerby_max_s"]) / 2, "var": 0})

    def observation_view(self, stop):
        item = self.observations.get(stop)
        stale = item is not None and (self.now() - item.measured_at).total_seconds() > MODEL["stale_s"]
        return {"value": item.waiting_count if item and not stale else None, "kind": "observed", "measured_at": item.measured_at.isoformat() if item else None, "source": item.source if item else None, "status": "stale" if stale else "ok" if item else "missing"}

    def _alert(self, kind, entity, active, evidence):
        if self.dataset != "live":
            return
        key = kind + ":" + entity
        old = self.alerts.get(key)
        if active:
            if not old or old["state"] == "resolved":
                old = {"id": key, "type": kind, "stop_id": entity.split(":")[0], "state": "open", "severity": "high" if kind in {"CAPACITY_RISK", "LEFT_BEHIND"} else "medium", "opened_at": self.now().isoformat()}
            old["evidence"] = evidence
            self.alerts[key] = old
        elif old and old["state"] != "resolved":
            old.update(state="resolved", resolved_at=self.now().isoformat(), clear_count=0)
        if old:
            self.store.put("alerts", key, old)

    def ack(self, key):
        item = self.alerts[key]
        if item["state"] == "resolved":
            raise ValueError("Resolved alert cannot be acknowledged")
        item.update(state="acknowledged", acked_at=self.now().isoformat())
        self.store.put("alerts", key, item)
        return item

    def forecast(self, route, scheduled, view_at=None):
        now = self.now()
        view_at = view_at or now
        seed = int(hashlib.sha256((scheduled["id"] + str(int(now.timestamp() // MODEL["recompute_s"]))).encode()).hexdigest()[:16], 16)
        rng = np.random.default_rng(seed)
        vehicle = next((v for v in self.vehicles.values() if v["event"]["trip_id"] == scheduled["id"]), None)
        start = timestamp(scheduled["startsAt"])
        delay = 0
        if vehicle:
            item = vehicle["event"]
            measured_arrival = timestamp(item["arrived_at"]) if "arrived_at" in item else timestamp(item["sim_time"]) + timedelta(seconds=item["eta_s"])
            delay = (measured_arrival - start).total_seconds() - route["offsets"][vehicle["index"]]
        last = (vehicle["index"] - (1 if "next_stop_id" in vehicle["event"] else 0)) if vehicle else -1
        people = np.full(MODEL["n_samples"], min(SIM["capacity"], vehicle["onboard"]) if vehicle else 0, dtype=int)
        passages = []
        for index, stop in enumerate(route["stops"]):
            arrival = start + timedelta(seconds=route["offsets"][index] + delay)
            stat = self._stat(route, stop["id"], arrival)
            previous = self.last_departures.get((route["id"], stop["id"]))
            gap = min(SIM["headway_s"], max(0, (arrival - previous).total_seconds())) if previous else SIM["headway_s"]
            mu = stat["rate"] * gap
            var = max(1, mu + stat["var"])
            obs = self.observations.get(stop["id"])
            live = obs and 0 <= (now - obs.measured_at).total_seconds() <= MODEL["stale_s"] and 0 <= (arrival - now).total_seconds() <= SIM["headway_s"] and (not previous or obs.measured_at >= previous)
            if live:
                adjusted = max(0, obs.waiting_count - stat["passersby"])
                dt = max(0, (arrival - obs.measured_at).total_seconds())
                live_mu = stat["share"] * adjusted + stat["rate"] * dt
                live_var = stat["share"] ** 2 * ((MODEL["camera_error"] * obs.waiting_count) ** 2 + MODEL["camera_base_variance"] + stat["passersby"]) + adjusted ** 2 * stat["share_var"] + stat["rate"] * dt + MODEL["aging_variance"] * (now - obs.measured_at).total_seconds()
                live_var = max(1, live_var)
                mu, var = (mu / var + live_mu / live_var) / (1 / var + 1 / live_var), 1 / (1 / var + 1 / live_var)
            if index <= last:
                passages.append({"stopId": stop["id"], "arrival": arrival.isoformat(), "departure": arrival.isoformat(), "arriving": None, "leaving": None, "percent": None, "alighting": 0, "boarding": 0, "leftBehind": 0, "status": "past"})
                continue
            arriving = float(np.mean(people))
            off = people.copy() if index == len(route["stops"]) - 1 else rng.binomial(people, min(1, stat["alpha"]))
            demand = np.zeros_like(people) if index == len(route["stops"]) - 1 else np.maximum(0, np.rint(rng.normal(mu, math.sqrt(var), people.size))).astype(int)
            on = np.minimum(demand, SIM["capacity"] - people + off)
            people = people - off + on
            risk = float(np.mean(on < demand))
            leaving = float(np.mean(people))
            percent = pct(leaving / SIM["capacity"])
            passage = {"stopId": stop["id"], "arrival": arrival.isoformat(), "departure": (arrival + timedelta(seconds=SIM["dwell_base_s"] + SIM["boarding_s"] * float(np.mean(on)) + SIM["alighting_s"] * float(np.mean(off)))).isoformat(), "arriving": round(arriving), "leaving": round(leaving), "percent": percent, "alighting": round(float(np.mean(off))), "boarding": round(float(np.mean(on))), "leftBehind": round(float(np.mean(demand - on))), "may_not_fit": risk > MODEL["risk_open"], "p_red": risk, "level": level(percent), "interval_80": np.quantile(people, [.1, .9]).tolist(), "confidence": None, "reliability": None, "generated_at": now.isoformat(), "kind": "predicted", "basis": "live-history" if live else "history-only", "model_version": "p0-averages"}
            passages.append(passage)
        at = view_at
        position_kind = "predicted" if at > now + timedelta(seconds=1) else "not-started" if at < start else "simulated-current"
        elapsed = (at - start).total_seconds() - delay
        idx = max(0, min(len(route["stops"]) - 1, next((i - 1 for i, offset in enumerate(route["offsets"]) if offset > elapsed), len(route["stops"]) - 1)))
        fraction = min(1, max(0, (elapsed - route["offsets"][idx]) / max(1, route["offsets"][min(idx + 1, len(route["stops"]) - 1)] - route["offsets"][idx])))
        points, anchors = self.geometry[route["id"]]
        progress = anchors[idx] + (anchors[min(idx + 1, len(anchors) - 1)] - anchors[idx]) * fraction
        segment = min(len(points) - 2, int(progress))
        position = {k: points[segment][axis] + (points[segment + 1][axis] - points[segment][axis]) * (progress - segment) for axis, k in enumerate(("lat", "lon"))}
        return {**scheduled, "capacity": SIM["capacity"], "seated_capacity": None, "passages": passages, "position": position, "positionKind": position_kind, "observed": {"people": vehicle["onboard"], "at": vehicle["at"], "kind": "observed", "source": "simulated"} if vehicle and (now - timestamp(vehicle["at"])).total_seconds() <= MODEL["stale_s"] else None, "reliability": None}

    def journey(self, origin, destination="", requested=None):
        if origin not in self.stops or (destination and destination not in self.stops):
            raise KeyError("Unknown stop")
        if origin == destination:
            raise ValueError("Departure and destination must differ")
        requested = requested or self.now()
        options = []
        for route in self.network["lines"]:
            starts = [i for i, s in enumerate(route["stops"]) if s["id"] == origin and i < len(route["stops"]) - 1]
            if not starts:
                continue
            first = starts[0]
            last = next((i for i, s in enumerate(route["stops"]) if i > first and s["id"] == destination), -1)
            if destination and last < 0:
                continue
            day = requested.replace(hour=0, minute=0, second=0, microsecond=0)
            runs = self.schedule(route, day) + self.schedule(route, day + timedelta(days=1))
            runs = [r for r in runs if timestamp(r["startsAt"]) + timedelta(seconds=route["offsets"][first]) >= requested][:3]
            options.append({"route": route, "trips": [self.forecast(route, r, requested) for r in runs], "originIndex": first, "destinationIndex": last})
        return {"options": options, "sim_time": self.now().isoformat()}

    def refresh(self):
        for stop in self.stops:
            self._alert("SENSOR_STALE", stop, self.observation_view(stop)["status"] != "ok", {"waiting": self.observation_view(stop)})
        now = self.now()
        for route in self.network["lines"]:
            runs = self.schedule(route, now.replace(hour=0, minute=0, second=0, microsecond=0))
            for run in runs:
                start = timestamp(run["startsAt"])
                if start <= now <= start + timedelta(seconds=route["offsets"][-1]):
                    result = self.forecast(route, run)
                    self.store.put("predictions", run["id"], result)
                    for passage in result["passages"]:
                        if passage["percent"] is None:
                            continue
                        key = passage["stopId"] + ":" + run["id"]
                        old = self.alerts.get("CAPACITY_RISK:" + key)
                        active = passage["p_red"] > MODEL["risk_open"] or (old and old["state"] != "resolved" and passage["p_red"] >= MODEL["risk_close"])
                        self._alert("CAPACITY_RISK", key, bool(active), {"trip_id": run["id"], "prediction": passage})
        self.dirty = False

    def display_stop(self, stop):
        options = self.journey(stop)["options"]
        buses = []
        for option in options:
            if not option["trips"]:
                continue
            p = option["trips"][0]["passages"][option["originIndex"]]
            buses.append(DisplayBus(line_id=option["route"]["name"], eta_s=max(0, int((timestamp(p["arrival"]) - self.now()).total_seconds())), predicted_onboard=p["leaving"], interval_80=p["interval_80"], level=p["level"], may_not_fit=p["may_not_fit"]))
        return DisplayPayload(stop_id=stop, generated_at=self.now(), buses=buses)
