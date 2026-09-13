"""
Why take layups? A risk analysis of shot distance under real New York weather.

The intuition every playground player already has - "it's windy, drive the lane" - turns out
to have a clean physical basis, and it is quantifiable.

The mechanism is flight time. Wind applies a roughly constant sideways acceleration, so the
sideways displacement it produces goes as t^2. Flight time in turn grows with distance. So
wind error does not grow linearly as you back up - it grows much faster than that, and the
catastrophic tail grows faster still.

Against that, the scoreboard pushes the other way: a three is worth 50% more than a layup.
This module computes both sides and weighs them.

The answer, measured: the extra point never covers the extra risk. In New York weather the
layup wins every month of the year, by +0.88 expected points per possession in calm July and
+1.55 in January. An earlier version of this analysis reported a seasonal crossover with
threes winning in summer - that was an artifact of treating light-and-variable wind as calm,
which flattered long shots and flattered them most in the summer months.

Caveat that matters: there is NO DEFENDER in this model. Every shot is uncontested. In a real
game the defense collapses toward the rim precisely because layups are high-percentage, which
is what makes a three worth attempting at all. What this measures is the WEATHER component of
shot value, not the whole of it.

    python3 -m analysis.shot_selection
"""
from __future__ import annotations

import math
import random
from collections import defaultdict

import numpy as np

from data_pipeline.climatology import load_observations, MonthlySampler
from physics.atmosphere import air_density
from physics.ball import NBA_BALL
from physics.solver import required_launch_speed
from physics.trajectory import simulate, backspin_vector, horizontal_distance_at_height

RIM_HEIGHT_M = 3.05
RELEASE_HEIGHT_M = 2.0
BACKSPIN_REV_S = 3.0
THREE_POINT_LINE_M = 7.24

# Make window: rim 45.7 cm less ball 23.9 cm, halved.
MAKE_WINDOW_M = (0.457 - 0.239) / 2.0
# "Catastrophe" = so far off that it is not a rim-out, it is a different outcome entirely.
CATASTROPHE_M = 0.30

INDOOR_TEMP_C, INDOOR_RH, INDOOR_PRESSURE_PA = 20.0, 40.0, 101_325.0

# Launch angle by distance. A short shot is thrown at a steeper arc; a long one flattens out.
# These are representative of real shooting form, not optimised - a genuine optimisation over
# angle is a good follow-up exercise.
SHOTS = [
    ("layup",        1.5,  58.0, 2),
    ("short 2",      3.0,  55.0, 2),
    ("mid-range",    4.5,  52.0, 2),
    ("long 2",       6.0,  50.0, 2),
    ("three",  THREE_POINT_LINE_M, 50.0, 3),
]

SAMPLES_PER_MONTH = 150


def landing_error(speed, angle_deg, distance_m, rho, wind):
    """Fire one shot and report (range error, lateral drift) at rim height, in metres."""
    angle = math.radians(angle_deg)
    v0 = np.array([speed * math.cos(angle), 0.0, speed * math.sin(angle)])
    traj = simulate(
        position=np.array([0.0, 0.0, RELEASE_HEIGHT_M]), velocity=v0,
        spin=backspin_vector(v0, BACKSPIN_REV_S), ball=NBA_BALL, air_density=rho,
        duration=8.0, dt=1e-3, wind=np.array(wind), stop_below_z=RIM_HEIGHT_M,
    )
    reached = horizontal_distance_at_height(traj, RIM_HEIGHT_M)
    if reached == 0.0:
        return None, None, traj.flight_time

    lateral = 0.0
    for i in range(len(traj.positions) - 1):
        z_here, z_next = traj.positions[i][2], traj.positions[i + 1][2]
        if z_next < z_here and z_here >= RIM_HEIGHT_M > z_next:
            f = (z_here - RIM_HEIGHT_M) / (z_here - z_next)
            lateral = float(
                traj.positions[i][1] + f * (traj.positions[i + 1][1] - traj.positions[i][1])
            )
            break
    return reached - distance_m, lateral, traj.flight_time


def main():
    observations, _ = load_observations()
    sampler = MonthlySampler(observations, seed=20260912)
    indoor_rho = air_density(INDOOR_TEMP_C, INDOOR_PRESSURE_PA, INDOOR_RH)

    print(f"Indoor reference: {INDOOR_TEMP_C} C, {INDOOR_RH}% RH -> rho = {indoor_rho:.4f}")
    print(f"Make window +/- {MAKE_WINDOW_M*100:.1f} cm    "
          f"catastrophe > {CATASTROPHE_M*100:.0f} cm\n")

    # Calibrate each shot so it goes in perfectly INDOORS, then see what weather does to it.
    calibrated = {}
    print(f"{'shot':<12}{'dist m':>8}{'angle':>7}{'speed m/s':>11}{'flight s':>10}")
    print("-" * 48)
    for name, distance, angle, _points in SHOTS:
        speed = required_launch_speed(
            distance, angle, RELEASE_HEIGHT_M, RIM_HEIGHT_M,
            NBA_BALL, indoor_rho, spin_rev_per_s=BACKSPIN_REV_S,
        )
        _, _, flight = landing_error(speed, angle, distance, indoor_rho, (0.0, 0.0, 0.0))
        calibrated[name] = speed
        print(f"{name:<12}{distance:>8.2f}{angle:>7.1f}{speed:>11.4f}{flight:>10.3f}")

    # PAIRED COMPARISON. Draw each month's weather ONCE, then fire every shot through that
    # same set of hours. Giving each shot its own random draw would mean the layup and the
    # three were judged on different weather, and the difference between them would carry the
    # sampling noise of two draws instead of none. Pairing removes that entirely: any gap
    # between two rows below is the shot, not the luck of the draw.
    #
    # Variable-direction hours are resolved HERE, once, and the resolved vector is stored.
    # Resolving inside the shot loop would draw a different direction for each shot and
    # destroy the pairing we just went to the trouble of establishing.
    wind_rng = random.Random(20260913)
    weather_by_month = {}
    for month in range(1, 13):
        hours = []
        for _ in range(SAMPLES_PER_MONTH):
            observation = sampler.sample(month)
            hours.append((
                air_density(
                    observation.temp_c, observation.pressure_pa,
                    observation.relative_humidity_pct,
                ),
                observation.wind_vector(0.0, rng=wind_rng),
            ))
        weather_by_month[month] = hours

    results = defaultdict(dict)
    for name, distance, angle, points in SHOTS:
        speed = calibrated[name]
        for month in range(1, 13):
            misses = []
            for rho, wind in weather_by_month[month]:
                range_err, lateral, _ = landing_error(speed, angle, distance, rho, wind)
                if range_err is None:
                    misses.append(float("inf"))     # never reached the rim - a total miss
                    continue
                misses.append(math.hypot(range_err, lateral))

            made = sum(1 for m in misses if m <= MAKE_WINDOW_M)
            disasters = sum(1 for m in misses if m > CATASTROPHE_M)
            results[name][month] = {
                "make_pct": 100.0 * made / len(misses),
                "catastrophe_pct": 100.0 * disasters / len(misses),
                "expected_points": points * made / len(misses),
            }

    names = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

    for metric, title in [
        ("make_pct", "MAKE % by month"),
        ("catastrophe_pct", f"CATASTROPHE % (miss > {CATASTROPHE_M*100:.0f} cm) by month"),
        ("expected_points", "EXPECTED POINTS PER SHOT (make% x shot value)"),
    ]:
        print(f"\n{title}")
        print(f"{'shot':<12}" + "".join(f"{n:>6}" for n in names))
        print("-" * (12 + 6 * 12))
        for name, _d, _a, _p in SHOTS:
            row = "".join(f"{results[name][m][metric]:>6.2f}" for m in range(1, 13))
            print(f"{name:<12}{row}")

    print("\nBEST SHOT BY EXPECTED POINTS, month by month")
    print(f"{'month':<8}{'best':<12}{'exp pts':>9}{'vs three':>10}")
    print("-" * 40)
    for month in range(1, 13):
        ranked = sorted(SHOTS, key=lambda s: -results[s[0]][month]["expected_points"])
        best = ranked[0][0]
        best_points = results[best][month]["expected_points"]
        three_points = results["three"][month]["expected_points"]
        print(f"{names[month-1]:<8}{best:<12}{best_points:>9.3f}{best_points-three_points:>+10.3f}")


if __name__ == "__main__":
    main()
