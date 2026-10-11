"""Adapted from colleague backend commit 0c87766, server/app/services/utils.py.

Retains clamped percentages and ordered threshold lookup; thresholds are now config-driven.
"""
from app.config import MODEL


def pct(fraction: float) -> int:
    return int(round(max(0.0, min(1.0, fraction)) * 100))


def crowd_label(occupancy_fraction: float) -> str:
    fraction = max(0.0, occupancy_fraction)
    for threshold, label in zip(MODEL["color_thresholds"], ("green", "yellow", "orange")):
        if fraction <= threshold:
            return label
    return "red"
