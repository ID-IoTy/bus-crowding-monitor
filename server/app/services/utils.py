"""Small shared helpers used across services."""
from __future__ import annotations

from app.config import CROWD_THRESHOLDS, utcnow  # noqa: F401  (re-exported)


def crowd_label(occupancy_fraction: float) -> str:
    """Map an occupancy fraction (0..1+) to a human label."""
    frac = max(0.0, occupancy_fraction)
    for threshold, label in CROWD_THRESHOLDS:
        if frac <= threshold:
            return label
    return "FULL"


def seconds_to_hhmm(seconds_from_midnight: float) -> str:
    """Format seconds-from-midnight as HH:MM (wraps past 24h)."""
    total_minutes = int(round(seconds_from_midnight / 60.0)) % (24 * 60)
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def pct(fraction: float) -> int:
    """Clamp a fraction to 0..100 and round to an int percentage."""
    return int(round(max(0.0, min(1.0, fraction)) * 100))
