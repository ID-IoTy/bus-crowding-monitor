"""Reproducible GTFS fixture, history replay, average training and OpenAPI export."""
import argparse
import json
from datetime import timedelta
from pathlib import Path
import numpy as np
from app.config import ROOT, SIM
from app.core.db import Store
from app.core.engine import Core, timestamp
from app.sim.world import World, schedule


def load_network():
    return json.loads((ROOT / "data/gtfs/network.json").read_text(encoding="utf-8"))


def train(store, network):
    buckets, waiting, last = {}, {}, {}
    with store.engine.connect() as db:
        from sqlalchemy import text
        rows = db.execute(text("SELECT type,payload FROM messages WHERE dataset='history' ORDER BY rowid"))
        for row in rows:
            event = json.loads(row.payload)
            if row.type == "observation" and event["trigger"] == "periodic":
                at = timestamp(event["measured_at"])
                key = f"waiting:{event['stop_id']}:{at.hour}:{'weekend' if at.weekday() >= 5 else 'weekday'}"
                waiting.setdefault(key, []).append(event["waiting_count"])
            if row.type != "departure":
                continue
            at = timestamp(event["doors_closed_at"])
            route = next(r for r in network["lines"] if r["name"] == event["line_id"] and r["direction"] == event["direction"])
            previous_key = (route["id"], event["stop_id"])
            previous = last.get(previous_key)
            last[previous_key] = at
            if event["onboard"] >= SIM["capacity"] * .95 or event["is_terminus"]:
                continue
            key = f"{route['id']}:{event['stop_id']}:{at.hour}:{'weekend' if at.weekday() >= 5 else 'weekday'}"
            bucket = buckets.setdefault(key, {"boarded": [], "gap": [], "off": [], "before": []})
            bucket["boarded"].append(event["boarded"])
            bucket["gap"].append(max(1, (at - previous).total_seconds()) if previous else SIM["headway_s"])
            bucket["off"].append(event["alighted"])
            bucket["before"].append(max(0, event["onboard"] - event["boarded"] + event["alighted"]))
    for key, data in buckets.items():
        rate = sum(data["boarded"]) / sum(data["gap"])
        stop = key.split(":")[1]
        n = len([r for r in network["lines"] if any(s["id"] == stop for s in r["stops"][:-1])])
        residual = np.array(data["boarded"]) - rate * np.array(data["gap"])
        store.put("model_stats", key, {"rate": rate, "alpha": min(1, sum(data["off"]) / max(1, sum(data["before"]))), "share": 1 / max(1, n), "share_var": .05 if n > 1 else 0, "passersby": SIM["passerby_per_minute"] / 60 * (SIM["passerby_min_s"] + SIM["passerby_max_s"]) / 2, "var": max(0, float(np.var(residual)) - float(np.mean(data["boarded"]))), "samples": len(residual)})
    for key, values in waiting.items():
        store.put("model_stats", key, {"mean": float(np.mean(values)), "var": float(np.var(values)), "samples": len(values)})
    return len(buckets)


def bootstrap(weeks=1):
    network = load_network()
    store = Store(f"sqlite:///{ROOT / 'backend/server.sqlite'}")
    from sqlalchemy import text
    with store.engine.begin() as db:
        db.execute(text("DELETE FROM messages WHERE dataset='history'"))
        db.execute(text("DELETE FROM model_stats"))
    start = timestamp(SIM["start_time"]).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(weeks=weeks)
    world = None
    core = Core(network, store, lambda: world.now, lambda r, d: schedule(network, r, d), "history")
    world = World(network, start, core, f"sqlite:///{ROOT / 'backend/sim.sqlite'}", batch=True)
    with store.engine.begin() as connection:
        store.bulk = connection
        world.run_until(start + timedelta(weeks=weeks))
    store.bulk = None
    print(f"Trained {train(store, network)} average buckets from {weeks} synthetic week(s).")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    boot = sub.add_parser("bootstrap")
    boot.add_argument("--weeks", type=int, default=1)
    export = sub.add_parser("export-openapi")
    export.add_argument("path")
    args = parser.parse_args()
    if args.command == "bootstrap":
        bootstrap(args.weeks)
    else:
        from app.main import app
        Path(args.path).write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
