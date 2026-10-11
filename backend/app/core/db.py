"""Core persistence, independent of simulator ground truth."""
import json
from sqlalchemy import create_engine, text


class Store:
    def __init__(self, url):
        self.engine = create_engine(url, connect_args={"check_same_thread": False})
        self.bulk = None
        with self.engine.begin() as db:
            db.execute(text("CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, type TEXT, dataset TEXT, payload TEXT)"))
            db.execute(text("CREATE TABLE IF NOT EXISTS model_stats (id TEXT PRIMARY KEY, payload TEXT)"))
            db.execute(text("CREATE TABLE IF NOT EXISTS alerts (id TEXT PRIMARY KEY, payload TEXT)"))
            db.execute(text("CREATE TABLE IF NOT EXISTS predictions (id TEXT PRIMARY KEY, payload TEXT)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS messages_dataset_type ON messages(dataset,type)"))

    def clear_live(self):
        with self.engine.begin() as db:
            db.execute(text("DELETE FROM messages WHERE dataset='live'"))
            db.execute(text("DELETE FROM alerts"))
            db.execute(text("DELETE FROM predictions"))

    def append(self, key, kind, dataset, payload):
        if self.bulk is not None:
            result = self.bulk.execute(text("INSERT OR IGNORE INTO messages VALUES (:id,:type,:dataset,:payload)"), {"id": key, "type": kind, "dataset": dataset, "payload": json.dumps(payload)})
            return result.rowcount == 1
        with self.engine.begin() as db:
            result = db.execute(text("INSERT OR IGNORE INTO messages VALUES (:id,:type,:dataset,:payload)"), {"id": key, "type": kind, "dataset": dataset, "payload": json.dumps(payload)})
        return result.rowcount == 1

    def put(self, table, key, payload):
        if table not in {"model_stats", "alerts", "predictions"}:
            raise ValueError("Unknown table")
        if self.bulk is not None:
            self.bulk.execute(text(f"INSERT OR REPLACE INTO {table} VALUES (:id,:payload)"), {"id": key, "payload": json.dumps(payload)})
            return
        with self.engine.begin() as db:
            db.execute(text(f"INSERT OR REPLACE INTO {table} VALUES (:id,:payload)"), {"id": key, "payload": json.dumps(payload)})

    def messages(self, dataset):
        with self.engine.connect() as db:
            return [(r.type, json.loads(r.payload)) for r in db.execute(text("SELECT type,payload FROM messages WHERE dataset=:dataset ORDER BY rowid"), {"dataset": dataset})]

    def stats(self):
        with self.engine.connect() as db:
            return {r.id: json.loads(r.payload) for r in db.execute(text("SELECT * FROM model_stats"))}
