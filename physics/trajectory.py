"""
The trajectory integrator - the heart of the project.

Coordinate system, fixed everywhere:
    x  horizontal, pointing from the shooter toward the hoop
    y  horizontal, pointing to the shooter's left
    z  straight up
Right-handed, so  x_hat cross y_hat = z_hat.
"""
from dataclasses import dataclass
import math
from typing import Optional

import numpy as np

from physics.ball import Ball

GRAVITY = 9.81
UP = np.array([0.0, 0.0, 1.0])


@dataclass
class Trajectory:
    """The full flight path. Keeping every sample makes plotting and debugging easy."""
    times: np.ndarray
    positions: np.ndarray   # shape (N, 3)
    velocities: np.ndarray  # shape (N, 3)

    @property
    def final_position(self) -> np.ndarray:
        return self.positions[-1]

    @property
    def flight_time(self) -> float:
        return float(self.times[-1])

    @property
    def apex_height(self) -> float:
        return float(np.max(self.positions[:, 2]))


def backspin_vector(velocity: np.ndarray, rev_per_s: float) -> np.ndarray:
    """
    Build the angular-velocity vector for a shot with `rev_per_s` of backspin.

    Backspin means the TOP of the ball travels backwards relative to the flight direction.
    Work it out with the right hand: ball heading +x, top surface moving -x, and the angular
    velocity vector points along -y.

    Getting this sign wrong makes backspin push the ball DOWN, which still produces a
    plausible-looking arc. That is what makes it dangerous, and why test T4 exists.

    Pass a negative rev_per_s for topspin.
    """
    horizontal = np.array([velocity[0], velocity[1], 0.0])
    speed = np.linalg.norm(horizontal)
    if speed < 1e-12:
        # A ball thrown straight up has no meaningful backspin axis.
        return np.zeros(3)

    direction = horizontal / speed
    # -(z_hat cross direction) is the backspin axis: for direction=+x this gives -y.
    return -(rev_per_s * 2.0 * math.pi) * np.cross(UP, direction)


def _acceleration(velocity, spin, ball, air_density, wind):
    """
    Total acceleration: gravity + drag + Magnus.

    Note it depends on velocity but not position. Air density is treated as uniform over the
    few metres a shot covers, which is correct to far better than we can measure.
    """
    accel = np.array([0.0, 0.0, -GRAVITY])

    v_rel = velocity - wind            # the air only knows about RELATIVE motion
    speed = np.linalg.norm(v_rel)
    if speed < 1e-12 or air_density <= 0.0:
        return accel

    # Drag: opposes relative motion, grows with the square of speed.
    #   a_drag = -(rho * Cd * A / 2m) * |v_rel| * v_rel
    drag_factor = air_density * ball.drag_coefficient * ball.area_m2 / (2.0 * ball.mass_kg)
    accel -= drag_factor * speed * v_rel

    # Magnus: a spinning ball drags air around with it, deflecting the flow and pushing
    # the ball perpendicular to both the spin axis and its motion.
    spin_rate = np.linalg.norm(spin)
    if spin_rate > 1e-12:
        # Spin parameter S: surface speed of the ball divided by its speed through the air.
        spin_parameter = spin_rate * ball.radius_m / speed
        lift_coefficient = min(ball.lift_max, ball.lift_slope * spin_parameter)

        lift_factor = air_density * lift_coefficient * ball.area_m2 / (2.0 * ball.mass_kg)
        spin_axis = spin / spin_rate
        accel += lift_factor * speed * np.cross(spin_axis, v_rel)

    return accel


def simulate(
    position, velocity, spin, ball: Ball, air_density: float,
    duration: float = 5.0, dt: float = 1e-3,
    wind=None, stop_below_z: Optional[float] = None,
) -> Trajectory:
    """
    Integrate the flight with classical Runge-Kutta (RK4).

    Why RK4 rather than the obvious `v += a*dt; r += v*dt`? That simpler scheme (Euler) has
    error proportional to dt, and it systematically ADDS energy - a ball in a vacuum would
    slowly climb, which would wreck test T3. RK4's error goes as dt^4, so at dt = 1 ms the
    trajectory is exact to well under a millimetre. It gets there by sampling the
    acceleration four times per step and taking a weighted average:

        k1 = f(y)              slope at the start
        k2 = f(y + dt/2 * k1)  slope at the midpoint, estimated using k1
        k3 = f(y + dt/2 * k2)  midpoint again, refined
        k4 = f(y + dt * k3)    slope at the end
        y_next = y + dt/6 * (k1 + 2*k2 + 2*k3 + k4)

    `stop_below_z` ends the flight once the ball has passed that height on the way DOWN,
    which is how you ask "where does it cross the rim's height?" without simulating the bounce.
    """
    position = np.asarray(position, dtype=float)
    velocity = np.asarray(velocity, dtype=float)
    spin = np.asarray(spin, dtype=float)
    wind = np.zeros(3) if wind is None else np.asarray(wind, dtype=float)

    if dt <= 0.0:
        raise ValueError(f"dt must be positive, got {dt}")

    def derivative(r, v):
        return v, _acceleration(v, spin, ball, air_density, wind)

    times, positions, velocities = [0.0], [position.copy()], [velocity.copy()]
    t, r, v = 0.0, position.copy(), velocity.copy()
    steps = int(duration / dt)

    for _ in range(steps):
        k1r, k1v = derivative(r, v)
        k2r, k2v = derivative(r + 0.5 * dt * k1r, v + 0.5 * dt * k1v)
        k3r, k3v = derivative(r + 0.5 * dt * k2r, v + 0.5 * dt * k2v)
        k4r, k4v = derivative(r + dt * k3r, v + dt * k3v)

        r = r + (dt / 6.0) * (k1r + 2.0 * k2r + 2.0 * k3r + k4r)
        v = v + (dt / 6.0) * (k1v + 2.0 * k2v + 2.0 * k3v + k4v)
        t += dt

        times.append(t)
        positions.append(r.copy())
        velocities.append(v.copy())

        # Only stop on the way down, or a shot launched from ground level would stop instantly.
        if stop_below_z is not None and v[2] < 0.0 and r[2] < stop_below_z:
            break

    return Trajectory(np.array(times), np.array(positions), np.array(velocities))


def horizontal_distance_at_height(trajectory: Trajectory, height_m: float) -> float:
    """
    How far had the ball travelled horizontally when it fell back through `height_m`?

    Linearly interpolates between the two samples that straddle the crossing. At dt = 1 ms the
    ball moves roughly 6 mm per step, over which a parabola is straight to about a micron - so
    the interpolation costs nothing in accuracy and saves shrinking dt.

    Returns 0.0 if the ball never got that high, which keeps the range solver monotonic.
    """
    positions = trajectory.positions
    start = positions[0]

    for i in range(len(positions) - 1):
        z_here, z_next = positions[i][2], positions[i + 1][2]
        descending = z_next < z_here
        if descending and z_here >= height_m > z_next:
            span = z_here - z_next
            fraction = (z_here - height_m) / span if span > 1e-15 else 0.0
            crossing = positions[i] + fraction * (positions[i + 1] - positions[i])
            return float(math.hypot(crossing[0] - start[0], crossing[1] - start[1]))

    return 0.0
