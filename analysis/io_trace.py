"""
Input/output trace of every key function in the codebase.

Run this to see, concretely, what each piece takes in and what it hands back. It is a
teaching artifact as much as a debugging one: run it after any physics change and read down
the page to see what moved.

    python3 -m analysis.io_trace
"""
import math

import numpy as np

from data_pipeline.climatology import (
    load_observations, monthly_summary, circular_mean_deg, MonthlySampler,
)
from physics.atmosphere import (
    air_density, saturation_vapour_pressure, altimeter_to_station_pressure,
)
from physics.ball import NBA_BALL
from physics.solver import required_launch_speed
from physics.trajectory import simulate, backspin_vector, horizontal_distance_at_height

RIM_HEIGHT_M = 3.05
RELEASE_HEIGHT_M = 2.0
THREE_POINT_M = 7.24
LAUNCH_ANGLE_DEG = 50.0
BACKSPIN_REV_S = 3.0


def rule(title):
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def show(label, value, unit=""):
    print(f"  {label:<44} {value:>16}  {unit}")


# ---------------------------------------------------------------- physics/ball.py
rule("physics/ball.py  —  Ball (a frozen dataclass of constants)")
print("  IN : nothing. These are measured properties of a regulation ball.")
print("  OUT:")
show("mass_kg", f"{NBA_BALL.mass_kg:.4f}", "kg")
show("circumference_m", f"{NBA_BALL.circumference_m:.4f}", "m")
show("radius_m          (derived)", f"{NBA_BALL.radius_m:.5f}", "m")
show("area_m2           (derived, pi*r^2)", f"{NBA_BALL.area_m2:.6f}", "m^2")
show("drag_coefficient", f"{NBA_BALL.drag_coefficient:.2f}", "dimensionless")
show("lift_slope / lift_max", f"{NBA_BALL.lift_slope:.2f} / {NBA_BALL.lift_max:.2f}", "")


# -------------------------------------------------------- physics/atmosphere.py
rule("physics/atmosphere.py  —  saturation_vapour_pressure(temp_c) -> Pa")
print("  IN : temperature in Celsius       OUT: max water-vapour pressure, pascals")
for t in (-5.0, 0.0, 20.0, 35.0, 100.0):
    show(f"temp_c = {t:>6.1f}", f"{saturation_vapour_pressure(t):>10.1f}", "Pa")

rule("physics/atmosphere.py  —  air_density(temp_c, pressure_pa, rh_pct) -> kg/m^3")
print("  IN : three scalars   OUT: one scalar. THIS is the only channel by which")
print("       weather reaches the ball. Everything else is bookkeeping.")
print()
for t, p, rh, note in [
    (0.0, 101325.0, 50.0, "freezing January"),
    (20.0, 101325.0, 40.0, "indoor stadium"),
    (30.0, 101325.0, 50.0, "hot July"),
    (20.0, 101325.0, 0.0, "bone dry, same temp as indoor"),
    (20.0, 101325.0, 100.0, "saturated, same temp as indoor"),
    (20.0, 98000.0, 40.0, "indoor temp, deep low-pressure system"),
]:
    rho = air_density(temp_c=t, pressure_pa=p, relative_humidity_pct=rh)
    show(f"{t:>5.1f}C {p/100:>7.1f}hPa {rh:>5.1f}%RH   ({note})", f"{rho:.5f}", "kg/m^3")

rule("physics/atmosphere.py  —  altimeter_to_station_pressure(inHg, elev_m) -> Pa")
print("  IN : the 'alti' field as reported (sea-level reduced) + station elevation")
print("  OUT: the pressure that actually exists where the ball is flying")
for alti in (29.42, 29.92, 30.45):
    station = altimeter_to_station_pressure(alti, 39.6)
    show(f"alti = {alti:.2f} inHg at 39.6 m", f"{station:>10.1f}", f"Pa  (raw {alti*3386.389:.1f})")


# ------------------------------------------------------- physics/trajectory.py
rule("physics/trajectory.py  —  backspin_vector(velocity, rev_per_s) -> omega vector")
print("  IN : a velocity vector + spin rate in revolutions/second")
print("  OUT: angular-velocity vector, rad/s. Sign here decides lift vs. dive.")
v_demo = np.array([6.13, 0.0, 7.31])
for rev in (0.0, 3.0, -3.0):
    w = backspin_vector(v_demo, rev)
    kind = "no spin" if rev == 0 else ("backspin -> lift" if rev > 0 else "topspin -> dive")
    show(f"rev_per_s = {rev:>5.1f}  ({kind})",
         f"[{w[0]:.2f} {w[1]:.2f} {w[2]:.2f}]", "rad/s")

rule("physics/trajectory.py  —  simulate(...) -> Trajectory")
print("  IN : position, velocity, spin, ball, air_density, wind, dt, stop_below_z")
print("  OUT: a Trajectory holding times[], positions[], velocities[]")
print()
indoor_rho = air_density(20.0, 101325.0, 40.0)
speed = required_launch_speed(
    THREE_POINT_M, LAUNCH_ANGLE_DEG, RELEASE_HEIGHT_M, RIM_HEIGHT_M,
    NBA_BALL, indoor_rho, spin_rev_per_s=BACKSPIN_REV_S,
)
angle = math.radians(LAUNCH_ANGLE_DEG)
v0 = np.array([speed * math.cos(angle), 0.0, speed * math.sin(angle)])
traj = simulate(
    position=np.array([0.0, 0.0, RELEASE_HEIGHT_M]), velocity=v0,
    spin=backspin_vector(v0, BACKSPIN_REV_S), ball=NBA_BALL, air_density=indoor_rho,
    duration=8.0, dt=1e-3, stop_below_z=RIM_HEIGHT_M,
)
show("input  speed", f"{speed:.4f}", "m/s")
show("input  velocity vector", f"[{v0[0]:.3f} {v0[1]:.3f} {v0[2]:.3f}]", "m/s")
show("output samples", f"{len(traj.times):,}", "(dt=1ms)")
show("output flight_time", f"{traj.flight_time:.4f}", "s")
show("output apex_height", f"{traj.apex_height:.4f}", "m")
show("output final_position", f"[{traj.final_position[0]:.3f} "
     f"{traj.final_position[1]:.3f} {traj.final_position[2]:.3f}]", "m")
print("\n  trajectory, sampled every 200 ms:")
print(f"    {'t (s)':>7}{'x (m)':>9}{'z (m)':>9}{'vx':>8}{'vz':>8}{'speed':>8}")
for i in range(0, len(traj.times), 200):
    t, p, v = traj.times[i], traj.positions[i], traj.velocities[i]
    print(f"    {t:>7.2f}{p[0]:>9.3f}{p[2]:>9.3f}{v[0]:>8.3f}{v[2]:>8.3f}"
          f"{np.linalg.norm(v):>8.3f}")

rule("physics/trajectory.py  —  horizontal_distance_at_height(traj, z) -> m")
print("  IN : a Trajectory + a height    OUT: horizontal distance at the descending crossing")
for z in (RIM_HEIGHT_M, 2.5, 0.0):
    d = horizontal_distance_at_height(traj, z)
    note = "" if d > 0 else "  <- never crossed (flight stopped at rim height)"
    show(f"height = {z:.2f} m", f"{d:.4f}", f"m{note}")


# ----------------------------------------------------------- physics/solver.py
rule("physics/solver.py  —  required_launch_speed(...) -> m/s")
print("  IN : target distance, angle, release height, rim height, ball, air_density")
print("  OUT: the release speed that drops the ball through the rim. Bisection, ~1e-4 m.")
print()
for t_c, label in [(0.0, "January air"), (20.0, "indoor"), (30.0, "July air")]:
    rho = air_density(t_c, 101325.0, 50.0)
    s = required_launch_speed(THREE_POINT_M, LAUNCH_ANGLE_DEG, RELEASE_HEIGHT_M,
                              RIM_HEIGHT_M, NBA_BALL, rho, spin_rev_per_s=BACKSPIN_REV_S)
    show(f"rho = {rho:.4f} kg/m^3   ({label})", f"{s:.4f}", "m/s")


# --------------------------------------------------- data_pipeline/climatology.py
rule("data_pipeline/climatology.py  —  circular_mean_deg(bearings) -> deg")
print("  IN : compass bearings   OUT: their true mean. The reason this function exists:")
for bearings, note in [
    ([350.0, 10.0], "arithmetic mean would say 180 (due SOUTH) - wrong by 180 degrees"),
    ([0.0, 90.0], "NE, as expected"),
    ([270.0, 280.0, 290.0], "no wraparound, agrees with the naive mean"),
]:
    show(f"{bearings}", f"{circular_mean_deg(bearings):.1f}", f"deg   {note}")

rule("data_pipeline/climatology.py  —  load_observations() -> [Observation], skipped")
observations, skipped = load_observations()
print("  IN : cached CSVs of raw ASOS text   OUT: SI-unit Observation records")
show("usable hours", f"{len(observations):,}", "")
show("rejected (missing/impossible)", f"{skipped:,}", f"({100*skipped/(len(observations)+skipped):.1f}%)")
print("\n  one record, raw fields -> SI:")
sample = observations[0]
show("month", sample.month, "")
show("temp_c            (from tmpf, F)", f"{sample.temp_c:.2f}", "C")
show("pressure_pa       (from alti, inHg)", f"{sample.pressure_pa:.1f}", "Pa")
show("relative_humidity_pct", f"{sample.relative_humidity_pct:.1f}", "%")
show("wind_speed_ms     (from sknt, kt)", f"{sample.wind_speed_ms:.3f}", "m/s")
show("wind_from_deg", f"{sample.wind_from_deg}", "deg (None = unavailable)")

rule("data_pipeline/climatology.py  —  Observation.wind_vector(court_bearing) -> (down, cross, 0)")
print("  IN : a court's compass bearing   OUT: wind in COURT coordinates")
print("       Same weather, two courts, completely different shot.")
from data_pipeline.climatology import Observation
gust = Observation(month=1, temp_c=2.0, pressure_pa=101000.0,
                   relative_humidity_pct=55.0, wind_speed_ms=6.0, wind_from_deg=270.0)
print(f"\n  weather: 6.0 m/s wind FROM 270 deg (a westerly)")
for bearing, label in [(0.0, "shooting north"), (90.0, "shooting east"),
                       (270.0, "shooting west"), (180.0, "shooting south")]:
    down, cross, _ = gust.wind_vector(bearing)
    kind = "tailwind" if down > 0.5 else ("headwind" if down < -0.5 else "pure crosswind")
    show(f"court bearing {bearing:>5.0f} deg ({label})",
         f"down {down:>+6.2f}  cross {cross:>+6.2f}", kind)

rule("data_pipeline/climatology.py  —  MonthlySampler.sample(month) -> Observation")
print("  IN : a month   OUT: ONE REAL OBSERVED HOUR drawn from that month's history.")
print("       Not a fitted curve. Every correlation between the variables is preserved,")
print("       because these numbers actually co-occurred in Central Park.")
print()
sampler = MonthlySampler(observations, seed=20260912)
print(f"    {'month':>6}{'temp C':>9}{'hPa':>9}{'RH %':>7}{'wind m/s':>10}{'from':>7}{'rho':>9}")
for month in (1, 4, 7, 10):
    for _ in range(3):
        o = sampler.sample(month)
        rho = air_density(o.temp_c, o.pressure_pa, o.relative_humidity_pct)
        direction = f"{o.wind_from_deg:.0f}" if o.wind_from_deg is not None else "n/a"
        print(f"    {o.month:>6}{o.temp_c:>9.1f}{o.pressure_pa/100:>9.1f}"
              f"{o.relative_humidity_pct:>7.0f}{o.wind_speed_ms:>10.2f}{direction:>7}{rho:>9.4f}")

rule("data_pipeline/climatology.py  —  monthly_summary(observations) -> dict")
print("  IN : all observations   OUT: per-month percentiles. This is the distribution")
print("       you are sampling FROM - shown so you can see it, not fitted to.")
summary = monthly_summary(observations)
names = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
print(f"\n    {'':5}{'hours':>7}{'calm':>7}{'no dir':>8}   {'temp C p10/p50/p90':^22}"
      f"{'wind m/s p50/p90/p99':^24}")
print("    " + "-" * 70)
for month in sorted(summary):
    d = summary[month]
    t, w = d["temp_c"], d["wind_ms"]
    print(f"    {names[month-1]:5}{d['hours']:>7,}{d['calm_pct']:>6.1f}%{d['dir_missing_pct']:>7.1f}%   "
          f"{t[10]:>6.1f}{t[50]:>7.1f}{t[90]:>7.1f}   "
          f"{w[50]:>7.1f}{w[90]:>8.1f}{w[99]:>8.1f}")
print("\n  'calm' = genuinely 0 m/s.  'no dir' = measurable wind, direction not reported.")
print("  Those are different failures and must not be added together.")
