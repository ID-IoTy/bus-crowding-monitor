"""Shared realistic demand patterns for the simulators."""
from __future__ import annotations

import math
import random


def demand_multiplier(hour: float) -> float:
    """Return a 0..1 demand multiplier peaking at the morning/evening rush.

    Two Gaussian humps centred at 08:00 and 18:00, plus a low baseline so the
    network is never completely idle during the day.
    """
    morning = math.exp(-((hour - 8.0) ** 2) / (2 * 1.1**2))
    evening = math.exp(-((hour - 18.0) ** 2) / (2 * 1.3**2))
    baseline = 0.15
    return min(1.0, baseline + 0.85 * max(morning, evening))


def weekday_multiplier(weekday: int) -> float:
    """Scale demand by day of week (0=Mon .. 6=Sun).

    Weekdays run at full demand; Saturday is lighter and the rush peaks flatten;
    Sunday is the quietest day.
    """
    if weekday <= 4:        # Mon-Fri
        return 1.0
    if weekday == 5:        # Saturday
        return 0.6
    return 0.45             # Sunday


def boarders_for(
    hour: float,
    stop_sequence: int,
    stops_total: int,
    rng: random.Random,
    weekday: int = 0,
) -> int:
    """How many people board at a stop given the time and position on route.

    Early stops (near the centre) attract more boardings during the morning;
    later stops see fewer boardings but more alightings. Weekend days are
    lighter via the weekday multiplier.
    """
    mult = demand_multiplier(hour) * weekday_multiplier(weekday)
    position_factor = 1.0 - 0.5 * (stop_sequence / max(1, stops_total - 1))
    expected = 10 * mult * position_factor
    return max(0, int(rng.gauss(expected, expected * 0.4 + 1)))


def alighters_for(occupancy: int, stop_sequence: int, stops_total: int, rng: random.Random) -> int:
    """How many people get off, growing towards the end of the route."""
    position_factor = 0.1 + 0.6 * (stop_sequence / max(1, stops_total - 1))
    expected = occupancy * position_factor
    return max(0, min(occupancy, int(rng.gauss(expected, expected * 0.3 + 1))))
