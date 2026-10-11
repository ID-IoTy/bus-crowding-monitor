"""Aggregate only the core archive, never simulator truth or live predictions.

History is immutable while the server is running. Bootstrap is an offline operation;
restart afterwards to invalidate the in-process archive cache.
"""
from datetime import date
from sqlalchemy import text
from app.config import MODEL
from app.contracts.history import HistoryView


def _archive(core):
    if hasattr(core, "history_archive"):
        return core.history_archive
    with core.store.engine.connect() as db:
        waiting = [dict(r._mapping) for r in db.execute(text("""
            SELECT json_extract(payload,'$.stop_id') stop,
                substr(json_extract(payload,'$.measured_at'),1,10) day,
                substr(json_extract(payload,'$.measured_at'),12,2) hour,
                SUM(json_extract(payload,'$.waiting_count')) total,
                COUNT(*) samples, MAX(json_extract(payload,'$.waiting_count')) peak
            FROM messages WHERE dataset='history' AND type='observation'
                AND json_extract(payload,'$.trigger')='periodic'
            GROUP BY stop, day, hour
        """))]
        vehicles = [dict(r._mapping) for r in db.execute(text("""
            SELECT json_extract(payload,'$.stop_id') stop,
                substr(json_extract(payload,'$.doors_closed_at'),1,10) day,
                substr(json_extract(payload,'$.doors_closed_at'),12,2) hour,
                json_extract(payload,'$.line_id') line,
                json_extract(payload,'$.direction') direction,
                SUM(json_extract(payload,'$.onboard')) total, COUNT(*) samples,
                SUM(CASE WHEN json_extract(payload,'$.onboard')>:threshold THEN 1 ELSE 0 END) high
            FROM messages WHERE dataset='history' AND type='departure'
            GROUP BY stop, day, hour, line, direction
        """), {"threshold": MODEL["capacity"] * MODEL["color_thresholds"][-1]})]
    core.history_archive = waiting, vehicles
    return core.history_archive


def history_view(core, capacity: int, high_load_percent: float, start: date | None = None,
                 end: date | None = None, route_id: str | None = None,
                 stop_id: str | None = None) -> HistoryView:
    if route_id is not None and route_id not in core.routes:
        raise LookupError("Unknown route pattern")
    if stop_id is not None and stop_id not in core.stops:
        raise LookupError("Unknown stop")
    if start and end and start > end:
        raise ValueError("Start must precede end")
    if start and end and (end - start).days >= MODEL["history_max_days"]:
        raise ValueError(f"Choose a range of at most {MODEL['history_max_days']} days")
    route = core.routes.get(route_id)
    stop_ids = {s["id"] for s in route["stops"]} if route else set(core.stops)
    if stop_id:
        stop_ids &= {stop_id}
    all_waiting, all_vehicles = _archive(core)
    days = sorted({r["day"] for r in all_waiting + all_vehicles})
    available_from = date.fromisoformat(days[0]) if days else None
    available_to = date.fromisoformat(days[-1]) if days else None
    start, end = start or available_from, end or available_to
    if start and end and start > end:
        raise ValueError("Start must precede end")
    if start and end and (end - start).days >= MODEL["history_max_days"]:
        raise ValueError(f"Choose a range of at most {MODEL['history_max_days']} days")

    def matches(row):
        return row["stop"] in stop_ids and start and end and str(start) <= row["day"] <= str(end)

    waiting = [r for r in all_waiting if matches(r)]
    vehicles = [r for r in all_vehicles if matches(r) and
                (not route or (r["line"] == route["name"] and r["direction"] == route["direction"]))]

    def aggregate(rows, key):
        result = {}
        for row in rows:
            group = result.setdefault(row[key], {"total": 0, "samples": 0, "peak": 0})
            group["total"] += row["total"]
            group["samples"] += row["samples"]
            group["peak"] = max(group["peak"], row.get("peak", 0))
        return result

    def mean(rows, scale=1):
        n = sum(r["samples"] for r in rows)
        return sum(r["total"] for r in rows) / n * scale if n else None

    def series(key):
        w, v = aggregate(waiting, key), aggregate(vehicles, key)
        labels = [f"{h:02d}" for h in range(24)] if key == "hour" else sorted(set(w) | set(v))
        def value(groups, label, scale):
            group = groups.get(label)
            return group["total"] / group["samples"] * scale if group else None
        return [{"label": f"{label}:00" if key == "hour" else label,
                 "waiting_mean": value(w, label, 1), "onboard_percent_mean": value(v, label, 100 / capacity),
                 "waiting_samples": w.get(label, {}).get("samples", 0),
                 "vehicle_samples": v.get(label, {}).get("samples", 0)} for label in labels]

    ranked = sorted(aggregate(waiting, "stop").items(), key=lambda pair: (-pair[1]["total"] / pair[1]["samples"], pair[0]))
    busiest = [{"stop_id": sid, "name": core.stops[sid]["name"], "mean_waiting": group["total"] / group["samples"],
                "peak_waiting": group["peak"], "samples": group["samples"]}
               for sid, group in ranked[:MODEL["history_ranking_limit"]]]
    vehicle_samples = sum(r["samples"] for r in vehicles)
    return HistoryView(generated_at=core.now(), available_from=available_from, available_to=available_to,
        start=start, end=end, route_id=route_id, stop_id=stop_id, capacity_assumed=capacity,
        summary={"waiting_mean": mean(waiting), "waiting_samples": sum(r["samples"] for r in waiting),
                 "observed_stops": len({r["stop"] for r in waiting}), "onboard_percent_mean": mean(vehicles, 100 / capacity),
                 "vehicle_samples": vehicle_samples,
                 "high_load_percent": 100 * sum(r["high"] for r in vehicles) / vehicle_samples if vehicle_samples else None},
        hourly=series("hour"), daily=series("day"), busiest_stops=busiest,
        notes=["Synthetic archived sensor observations, not real passenger statistics.",
               "Waiting means are periodic-sample averages; shared-stop counts include every line.",
               "Bus occupancy is sampled after departure, not a time-weighted fleet average.",
               f"High load is the share of departure readings above {high_load_percent:g}% assumed occupancy.",
               "No calibrated accuracy, abandonment or sensor-uptime metric is inferred from this archive."])
