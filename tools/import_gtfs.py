"""Extract two route patterns per GTT line for the frontend demo.
Run: python tools/import_gtfs.py gtt_gtfs.zip frontend/public/network.json
No live passenger counts or arrival predictions are imported.
"""
import collections
import csv
import io
import json
from pathlib import Path
import sys
import zipfile

def extract(archive, output):
    with zipfile.ZipFile(archive) as feed:
        def rows(name):
            return csv.DictReader(io.TextIOWrapper(feed.open(name), encoding="utf-8-sig"))
        metadata = next(rows("feed_info.txt"))
        routes = {r["route_id"]: r for r in rows("routes.txt") if r["route_short_name"] in ("18", "68", "33", "42") and r["route_type"] == "3"}
        stops = {r["stop_id"]: r for r in rows("stops.txt")}
        trips = {r["trip_id"]: r for r in rows("trips.txt") if r["route_id"] in routes}
        times = collections.defaultdict(list)
        for row in rows("stop_times.txt"):
            if row["trip_id"] in trips:
                times[row["trip_id"]].append(row)
        shape_groups = collections.defaultdict(list)
        for trip_id, trip in trips.items():
            if times[trip_id]:
                shape_groups[(trip["route_id"], trip["direction_id"])].append(trip_id)
        selected = []
        for key, ids in sorted(shape_groups.items()):
            common_shape = collections.Counter(trips[i]["shape_id"] for i in ids).most_common(1)[0][0]
            candidates = [i for i in ids if trips[i]["shape_id"] == common_shape]
            chosen = max(candidates, key=lambda i: len(times[i]))
            selected.append((key, chosen, common_shape))
        wanted_shapes = {shape for _, _, shape in selected}
        shapes = collections.defaultdict(list)
        for row in rows("shapes.txt"):
            if row["shape_id"] in wanted_shapes:
                shapes[row["shape_id"]].append((int(row["shape_pt_sequence"]), float(row["shape_pt_lat"]), float(row["shape_pt_lon"])))
        lines = []
        for (route_id, direction), trip_id, shape in selected:
            route = routes[route_id]
            sequence = sorted(times[trip_id], key=lambda r: int(r["stop_sequence"]))
            lines.append({
                "id": route_id + "-" + direction, "routeId": route_id,
                "name": route["route_short_name"], "description": route["route_long_name"],
                "direction": direction, "headsign": trips[trip_id]["trip_headsign"],
                "color": {"18": "#197d67", "68": "#546bc8", "33": "#bc6b24", "42": "#a04788"}[route["route_short_name"]],
                "stops": [{"id": r["stop_id"], "name": stops[r["stop_id"]]["stop_name"],
                           "lat": float(stops[r["stop_id"]]["stop_lat"]), "lon": float(stops[r["stop_id"]]["stop_lon"])} for r in sequence],
                "shape": [[lat, lon] for _, lat, lon in sorted(shapes[shape])]
            })
        data = {"source": "GTT static GTFS", "sourceUrl": "https://www.gtt.to.it/open_data/gtt_gtfs.zip",
                "feedVersion": metadata["feed_version"], "feedStartDate": metadata["feed_start_date"],
                "feedEndDate": metadata["feed_end_date"], "importedDate": "2026-10-10",
                "note": "One common full trip pattern per direction. Other route variants are omitted. Reuse terms require confirmation before public redistribution.",
                "lines": lines}
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(json.dumps({"patterns": [{"id": x["id"], "headsign": x["headsign"], "stops": len(x["stops"])} for x in lines]}, indent=2))
if __name__ == "__main__":
    extract(sys.argv[1], sys.argv[2])
