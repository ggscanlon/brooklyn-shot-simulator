"""
Turn raw ASOS observations into weather the simulator can use.

THE CENTRAL DESIGN DECISION LIVES HERE.

There are two ways to turn ten years of history into "a January day in Brooklyn":

  (A) FIT a distribution to each variable - say, a normal for temperature, a Weibull for
      wind speed - then draw each variable independently from its fitted curve.

  (B) RESAMPLE: pick one real observed hour out of every January in the record, and use
      all of its numbers together.

This module does (B), deliberately. The reason is correlation. Temperature, pressure, wind
and humidity are not independent in the real atmosphere. A cold January hour in New York is
disproportionately likely to be a windy one, because that is what a nor'easter is - and
high pressure days are calm and clear. If you fit four separate marginal distributions and
sample them independently, you will cheerfully generate 30 C with a 1040 hPa high and a
20 m/s gale, which is not a thing that happens.

Resampling whole observed hours preserves every one of those correlations for free, and
requires no assumption about distributional shape. The cost is that you can never generate
an hour more extreme than the worst one in the record - which for a basketball game is a
feature, not a bug.

`monthly_summary()` still reports the fitted-style percentiles, because you should look at
the distribution you are sampling from even when you are not fitting a curve to it.
"""
from __future__ import annotations

import csv
import dataclasses
import math
import pathlib
import random
from collections import defaultdict
from typing import Iterable, Optional

KNOTS_TO_MS = 0.514444
INHG_TO_PA = 3386.389

# NWS Central Park (KNYC). The altimeter field is reduced to sea level, so this elevation is
# what converts it back to the pressure the ball actually flies through. Published values for
# this station vary between about 39 and 48 m; at 0.012% density per metre the choice moves
# the answer far less than the weather does, but it should be stated rather than assumed.
KNYC_ELEVATION_M = 39.6

RAW_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"


@dataclasses.dataclass(frozen=True)
class Observation:
    """One hour of weather, in SI units, ready for the physics."""
    month: int
    temp_c: float
    pressure_pa: float          # station pressure, not sea-level reduced
    relative_humidity_pct: float
    wind_speed_ms: float
    wind_from_deg: Optional[float]   # None when calm - direction is meaningless at 0 speed

    def wind_vector(self, court_bearing_deg: float = 0.0):
        """
        Convert to a (downcourt, cross-court, vertical) wind vector for the simulator.

        Two traps live in this conversion and both are silent if you get them wrong:

        1. METAR reports the direction wind blows FROM, not toward. A "270" wind is a
           westerly, and it pushes the ball toward the EAST. Forgetting the 180-degree flip
           reverses every outdoor result while still looking completely reasonable.

        2. Compass bearings run clockwise from north; mathematical angles run anticlockwise
           from east. They are not the same coordinate system.

        `court_bearing_deg` is the compass direction the shooter faces. Rotating into court
        coordinates is what makes one Brooklyn court play differently from another.
        """
        if self.wind_from_deg is None or self.wind_speed_ms <= 0.0:
            return (0.0, 0.0, 0.0)

        # Direction the air is travelling toward, relative to the way the shooter faces.
        toward = math.radians((self.wind_from_deg + 180.0) - court_bearing_deg)
        downcourt = self.wind_speed_ms * math.cos(toward)   # +ve = tailwind
        cross = -self.wind_speed_ms * math.sin(toward)      # +ve = pushes to shooter's left
        return (downcourt, cross, 0.0)


def _number(raw: str) -> Optional[float]:
    """
    Parse one ASOS field.

    'M' means missing. 'T' means a trace of precipitation - a real observation, but not a
    number, and it appears in fields you would not expect. Anything unparseable becomes None
    rather than a zero, because a silent zero is a wrong measurement wearing a disguise.
    """
    raw = raw.strip()
    if raw in ("", "M", "T", "null", "None"):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def load_observations(station: str = "nyc", years: Iterable[int] = range(2015, 2025)):
    """Read the cached CSVs, convert to SI, drop hours that are missing anything essential."""
    observations, skipped = [], 0

    for year in years:
        path = RAW_DIR / f"{station}_{year}.csv"
        if not path.exists():
            continue

        with path.open() as handle:
            for row in csv.DictReader(handle):
                temp_f = _number(row.get("tmpf", ""))
                humidity = _number(row.get("relh", ""))
                altimeter = _number(row.get("alti", ""))
                speed_kt = _number(row.get("sknt", ""))
                direction = _number(row.get("drct", ""))

                # Temperature, humidity and pressure are load-bearing: no air density without
                # them. Wind direction is allowed to be missing, because calm hours report it
                # as missing and those hours are perfectly usable.
                if None in (temp_f, humidity, altimeter, speed_kt):
                    skipped += 1
                    continue
                if not (-40.0 <= temp_f <= 130.0 and 0.0 <= humidity <= 100.0):
                    skipped += 1          # physically impossible - a sensor fault
                    continue
                if not (25.0 <= altimeter <= 32.0):
                    skipped += 1
                    continue

                speed_ms = speed_kt * KNOTS_TO_MS
                # Calm: direction carries no information. Storing 0 here would silently mean
                # "due north" and bias every wind statistic toward it.
                if speed_ms <= 0.0 or direction is None:
                    direction = None

                sea_level_pa = altimeter * INHG_TO_PA
                station_pa = sea_level_pa * (
                    1.0 - (0.0065 * KNYC_ELEVATION_M) / 288.15
                ) ** 5.2559

                observations.append(Observation(
                    month=int(row["valid"][5:7]),
                    temp_c=(temp_f - 32.0) * 5.0 / 9.0,
                    pressure_pa=station_pa,
                    relative_humidity_pct=humidity,
                    wind_speed_ms=speed_ms,
                    wind_from_deg=direction,
                ))

    return observations, skipped


def circular_mean_deg(directions: Iterable[float]) -> Optional[float]:
    """
    Average a set of compass bearings.

    A plain arithmetic mean is WRONG here and wrong in a way that looks fine. Average 350 and
    10 the obvious way and you get 180 - due south, when the answer is due north. The fix is
    to average the unit vectors and take the angle of the result.
    """
    values = [d for d in directions if d is not None]
    if not values:
        return None
    sin_sum = sum(math.sin(math.radians(d)) for d in values)
    cos_sum = sum(math.cos(math.radians(d)) for d in values)
    if abs(sin_sum) < 1e-12 and abs(cos_sum) < 1e-12:
        return None            # perfectly opposed directions - no meaningful mean

    mean = math.degrees(math.atan2(sin_sum, cos_sum)) % 360.0
    # Guard the wrap point. Averaging 350 and 10 lands a hair below zero in floating point,
    # and Python's modulo turns that into 359.9999999999997, which then prints as "360" -
    # correct, but it reads as a bug to anyone checking the answer by hand.
    if mean > 360.0 - 1e-9:
        mean = 0.0
    return mean


def percentile(values, q: float) -> float:
    """Linear-interpolated percentile. q in [0, 100]."""
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    pos = (len(ordered) - 1) * q / 100.0
    low, high = math.floor(pos), math.ceil(pos)
    if low == high:
        return ordered[int(pos)]
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def monthly_summary(observations):
    """
    Per-month distribution of each input variable.

    This is what you look at to understand the weather you are sampling from, even though the
    simulator draws whole observed hours rather than reading these numbers.
    """
    by_month = defaultdict(list)
    for observation in observations:
        by_month[observation.month].append(observation)

    summary = {}
    for month in sorted(by_month):
        rows = by_month[month]
        # These two are NOT the same thing and must never be merged into one "calm" number.
        # A genuinely calm hour is weather. An hour with measurable wind but no reported
        # direction is an instrument gap, and Central Park has a lot of them.
        truly_calm = sum(1 for r in rows if r.wind_speed_ms == 0.0)
        direction_missing = sum(
            1 for r in rows if r.wind_from_deg is None and r.wind_speed_ms > 0.0
        )
        summary[month] = {
            "hours": len(rows),
            "calm_pct": 100.0 * truly_calm / len(rows),
            "dir_missing_pct": 100.0 * direction_missing / len(rows),
            "temp_c": {q: percentile([r.temp_c for r in rows], q) for q in (10, 50, 90)},
            "pressure_pa": {q: percentile([r.pressure_pa for r in rows], q) for q in (10, 50, 90)},
            "humidity_pct": {q: percentile([r.relative_humidity_pct for r in rows], q) for q in (10, 50, 90)},
            "wind_ms": {q: percentile([r.wind_speed_ms for r in rows], q) for q in (10, 50, 90, 99)},
            "wind_from_deg": circular_mean_deg([r.wind_from_deg for r in rows]),
        }
    return summary


class MonthlySampler:
    """
    Draws a real observed hour from a chosen month.

    This is option (B) from the module docstring: no fitted curve, no independence assumption,
    every correlation between the variables preserved exactly as the atmosphere produced it.
    """

    def __init__(self, observations, seed: Optional[int] = None):
        self._by_month = defaultdict(list)
        for observation in observations:
            self._by_month[observation.month].append(observation)
        self._random = random.Random(seed)

    def sample(self, month: int) -> Observation:
        pool = self._by_month.get(month)
        if not pool:
            raise ValueError(f"no observations for month {month}")
        return self._random.choice(pool)

    def available_months(self):
        return sorted(self._by_month)
