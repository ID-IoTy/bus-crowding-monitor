"""Central configuration for the SmartBus server.

All tunable constants live here so the rest of the code never hard-codes
magic numbers. Values can be overridden with environment variables.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path


def utcnow() -> datetime:
    """Timezone-naive UTC now (SQLite columns store naive datetimes)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent.parent  # the `server/` directory
DB_PATH = BASE_DIR / "transport.db"
MODEL_PATH = BASE_DIR / "ml" / "model.joblib"

DATABASE_URL = os.getenv("SMARTBUS_DATABASE_URL", f"sqlite:///{DB_PATH}")

# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #
# Devices (buses + stops) and the public app use this key.
API_KEY = os.getenv("SMARTBUS_API_KEY", "dev-key")
# The transport company's admin tooling uses a stronger, separate key.
ADMIN_API_KEY = os.getenv("SMARTBUS_ADMIN_API_KEY", "admin-key")
API_KEY_HEADER = "X-API-Key"

# --------------------------------------------------------------------------- #
# Domain constants
# --------------------------------------------------------------------------- #
BUS_CAPACITY = 75  # maximum passengers per bus

# Correlation: how long after a bus-event we still accept a matching stop-event.
CORRELATION_WINDOW_SECONDS = 30

# ETA / dwell model
BASE_DWELL_SECONDS = 8          # fixed time the bus is stopped even with 0 boarders
SECONDS_PER_BOARDING = 3.0      # extra dwell per boarding passenger
SECONDS_PER_ALIGHTING = 1.5     # extra dwell per alighting passenger

# Crowdedness label thresholds (fraction of capacity)
CROWD_THRESHOLDS = [
    (0.40, "LOW"),
    (0.65, "MEDIUM"),
    (0.85, "HIGH"),
    (1.01, "FULL"),  # 1.01 so that exactly 100% still maps to FULL
]

# Anomaly detection thresholds
OVERCROWDING_OCCUPANCY = 0.90      # > 90% full
ABNORMAL_CROWD_GROWTH = 0.50       # +50% vs rolling average
ABANDONMENT_DROP = 0.40            # -40% drop without a bus arriving

# --------------------------------------------------------------------------- #
# Network topology (seed data)
# --------------------------------------------------------------------------- #
STOPS_PER_ROUTE = 40
ROUTES = {
    "R1": {"name": "Route 1 - Centro / Lingotto", "buses": ["BUS-01"]},
    "R2": {"name": "Route 2 - Mirafiori / Porta Nuova", "buses": ["BUS-02", "BUS-03"]},
}

# Rough Turin bounding box used to scatter synthetic stop coordinates.
TURIN_LAT = 45.0703
TURIN_LON = 7.6869
