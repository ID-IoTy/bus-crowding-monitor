"""Use existing GTFS extraction and retain the selected trips' planned stop offsets."""
import csv
import io
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
network = json.loads((root / "frontend/public/network.json").read_text(encoding="utf-8"))
network["lines"] = [line for line in network["lines"] if line["name"] in ("33", "42")]
with zipfile.ZipFile(root / "gtt_gtfs.zip") as archive:
    def rows(name):
        return csv.DictReader(io.TextIOWrapper(archive.open(name), encoding="utf-8-sig"))
    trips = {t["trip_id"]: t for t in rows("trips.txt") if t["route_id"] in {l["routeId"] for l in network["lines"]}}
    times = {}
    for row in rows("stop_times.txt"):
        if row["trip_id"] in trips:
            times.setdefault(row["trip_id"], []).append(row)
    def seconds(text):
        h, m, s = map(int, text.split(":"))
        return h * 3600 + m * 60 + s
    for line in network["lines"]:
        candidates = [sorted(times[k], key=lambda t: int(t["stop_sequence"])) for k, t in trips.items() if t["route_id"] == line["routeId"] and t["direction_id"] == line["direction"] and k in times]
        match = next((sequence for sequence in candidates if [t["stop_id"] for t in sequence] == [s["id"] for s in line["stops"]]), None)
        if match is None:
            raise ValueError(f"No GTFS timing match for {line['id']}")
        base = seconds(match[0]["departure_time"])
        line["offsets"] = [seconds(t["arrival_time"]) - base for t in match]
        if any(b <= a for a, b in zip(line["offsets"], line["offsets"][1:])):
            raise ValueError("Non-increasing GTFS offsets")
(root / "data/gtfs").mkdir(parents=True, exist_ok=True)
(root / "data/gtfs/network.json").write_text(json.dumps(network, ensure_ascii=False), encoding="utf-8")
print([(line["id"], line["offsets"][-1]) for line in network["lines"]])
