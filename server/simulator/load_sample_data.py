"""Load the sample-week JSONL payloads into the database.

This replays the example API payloads through the SAME code paths the live
server uses (store + correlate), so the database ends up with:
  - bus_events
  - stop_events
  - correlated_events   <-- what ml/train.py learns from

In other words, the sample data feeds the model exactly as production traffic
would. Run the seeder first so routes/stops/buses exist.

Run with:
    python seeder.py
    python -m simulator.load_sample_data
    python -m ml.train
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from app.config import (
    BASE_DWELL_SECONDS,
    CORRELATION_WINDOW_SECONDS,
    SECONDS_PER_ALIGHTING,
    SECONDS_PER_BOARDING,
)
from app.db.database import Base, SessionLocal, engine
import app.models  # noqa: F401
from app.models.events import BusEvent, CorrelatedEvent, StopEvent
from app.models.route import Stop

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", ""))


def _merge_streams(bus_path: Path, stop_path: Path) -> list[tuple[str, dict]]:
    """Return all events tagged by kind, ordered by timestamp (as a real log)."""
    events: list[tuple[str, dict]] = []
    for line in bus_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(("bus", json.loads(line)))
    for line in stop_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(("stop", json.loads(line)))
    events.sort(key=lambda e: e[1]["timestamp"])
    return events


def _bulk_correlate(db) -> None:
    """Reconstruct correlated_events for the whole dataset efficiently.

    Mirrors the per-event logic in app/services/correlator.py:
      - occupancy_before = occupancy at the bus's previous (earlier-sequence) stop
      - people_boarded   = max(0, after - before)
      - people_alighted  = max(0, before + boarded - after)
      - dwell            = base + boarded*board_s + alighted*alight_s
    """
    seq_by_stop = {s.id: s.sequence for s in db.query(Stop).all()}

    pre_by_stop: dict[str, list[StopEvent]] = {}
    post_by_stop: dict[str, list[StopEvent]] = {}
    for se in db.query(StopEvent).all():
        if se.event_type == "pre_arrival":
            pre_by_stop.setdefault(se.stop_id, []).append(se)
        elif se.event_type == "post_departure":
            post_by_stop.setdefault(se.stop_id, []).append(se)
    for lst in (*pre_by_stop.values(), *post_by_stop.values()):
        lst.sort(key=lambda e: e.timestamp)

    def nearest(lst, ts):
        best, best_dt = None, None
        for e in lst:
            dt = abs((e.timestamp - ts).total_seconds())
            if dt > CORRELATION_WINDOW_SECONDS:
                continue
            if best_dt is None or dt < best_dt:
                best, best_dt = e, dt
        return best

    # Bus events grouped per bus, ordered so we can read the previous occupancy.
    bus_events = db.query(BusEvent).order_by(BusEvent.bus_id, BusEvent.timestamp, BusEvent.id).all()
    last_occ_by_bus: dict[str, int] = {}

    correlated: list[dict] = []
    for be in bus_events:
        pre = nearest(pre_by_stop.get(be.stop_id, []), be.timestamp)
        post = nearest(post_by_stop.get(be.stop_id, []), be.timestamp)
        prev_occ = last_occ_by_bus.get(be.bus_id)
        # Update running occupancy memory for this bus regardless.
        last_occ_by_bus[be.bus_id] = be.passengers_onboard

        if pre is None or post is None:
            continue

        occupancy_before = prev_occ if prev_occ is not None else be.passengers_onboard
        occupancy_after = be.passengers_onboard
        boarded = max(0, occupancy_after - occupancy_before)
        alighted = max(0, occupancy_before + boarded - occupancy_after)
        dwell = BASE_DWELL_SECONDS + boarded * SECONDS_PER_BOARDING + alighted * SECONDS_PER_ALIGHTING

        correlated.append({
            "bus_id": be.bus_id,
            "route_id": be.route_id,
            "stop_id": be.stop_id,
            "timestamp": be.timestamp,
            "occupancy_before": occupancy_before,
            "occupancy_after": occupancy_after,
            "waiting_before": pre.people_waiting,
            "waiting_after": post.people_waiting,
            "people_boarded": boarded,
            "people_alighted": alighted,
            "dwell_time_seconds": dwell,
        })
    db.bulk_insert_mappings(CorrelatedEvent, correlated)


def load(wipe: bool = True) -> tuple[int, int, int]:
    bus_path = SAMPLE_DIR / "bus_events_week.jsonl"
    stop_path = SAMPLE_DIR / "stop_events_week.jsonl"
    if not bus_path.exists() or not stop_path.exists():
        raise SystemExit(
            "Sample files not found. Generate them first:\n"
            "    python -m simulator.generate_sample_week"
        )

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if wipe:
            for model in (CorrelatedEvent, BusEvent, StopEvent):
                db.query(model).delete()
            db.commit()

        # --- Pass 1: fast bulk insert of every raw event ------------------
        bus_rows: list[dict] = []
        stop_rows: list[dict] = []
        for kind, body in _merge_streams(bus_path, stop_path):
            ts = _parse_ts(body["timestamp"])
            if kind == "bus":
                bus_rows.append({
                    "bus_id": body["bus_id"],
                    "route_id": body["route_id"],
                    "stop_id": body["stop_id"],
                    "timestamp": ts,
                    "passengers_onboard": body["passengers_onboard"],
                    "door_status": body.get("door_status", "closed"),
                    "speed_kmh": body.get("speed_kmh", 0.0),
                    "latitude": body.get("latitude"),
                    "longitude": body.get("longitude"),
                })
            else:
                stop_rows.append({
                    "stop_id": body["stop_id"],
                    "timestamp": ts,
                    "people_waiting": body["people_waiting"],
                    "event_type": body.get("event_type", "periodic"),
                })
        db.bulk_insert_mappings(BusEvent, bus_rows)
        db.bulk_insert_mappings(StopEvent, stop_rows)
        db.commit()
        n_bus, n_stop = len(bus_rows), len(stop_rows)

        # --- Pass 2: bulk correlation in memory ----------------------------
        # Same math as app/services/correlator.py, but computed in Python over
        # in-memory indexes so we avoid thousands of per-row queries/commits.
        _bulk_correlate(db)
        db.commit()

        n_corr = db.query(CorrelatedEvent).count()
        print("Sample data loaded into the database:")
        print(f"  bus_events:        {n_bus}")
        print(f"  stop_events:       {n_stop}")
        print(f"  correlated_events: {n_corr}  (training set for ml/train.py)")
        return n_bus, n_stop, n_corr
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load sample-week payloads into the DB.")
    parser.add_argument("--keep", action="store_true", help="append instead of wiping history")
    args = parser.parse_args()
    load(wipe=not args.keep)
