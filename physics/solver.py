"""
Inverse problems: not "where does this shot land?" but "what shot lands there?"

The simulator answers the forward question. A game needs the backward one - given a target,
how hard do you have to throw? There is no closed-form answer once drag is involved, so we
search for it numerically.
"""
import math

import numpy as np

from physics.ball import Ball
from physics.trajectory import simulate, backspin_vector, horizontal_distance_at_height


def required_launch_speed(
    horizontal_distance_m: float,
    launch_angle_deg: float,
    launch_height_m: float,
    target_height_m: float,
    ball: Ball,
    air_density: float,
    spin_rev_per_s: float = 0.0,
    wind=None,
    dt: float = 1e-3,
    tolerance_m: float = 1e-4,
    max_iterations: int = 60,
) -> float:
    """
    Find the release speed that drops the ball through `target_height_m` at exactly
    `horizontal_distance_m` away.

    Uses bisection, which works because the range is monotonic in launch speed at a fixed
    angle - throw harder, land further. Bisection is slower to converge than Newton's method
    but it cannot diverge, and robustness beats speed for something a beginner will be
    poking at. Each halving buys one more bit of precision, so ~40 iterations is plenty.

    Raises ValueError if the target is out of reach even at 30 m/s, rather than silently
    returning a wrong answer - a solver that confidently reports nonsense is worse than one
    that admits defeat.
    """
    angle = math.radians(launch_angle_deg)

    def distance_for(speed: float) -> float:
        velocity = np.array([speed * math.cos(angle), 0.0, speed * math.sin(angle)])
        spin = backspin_vector(velocity, spin_rev_per_s) if spin_rev_per_s else np.zeros(3)
        traj = simulate(
            position=np.array([0.0, 0.0, launch_height_m]),
            velocity=velocity, spin=spin, ball=ball, air_density=air_density,
            duration=8.0, dt=dt, wind=wind, stop_below_z=target_height_m,
        )
        return horizontal_distance_at_height(traj, target_height_m)

    low, high = 0.1, 30.0
    if distance_for(high) < horizontal_distance_m:
        raise ValueError(
            f"cannot reach {horizontal_distance_m} m at {launch_angle_deg} deg "
            f"even at {high} m/s - try a different angle"
        )

    for _ in range(max_iterations):
        mid = 0.5 * (low + high)
        reached = distance_for(mid)

        if abs(reached - horizontal_distance_m) < tolerance_m:
            return mid
        if reached < horizontal_distance_m:
            low = mid
        else:
            high = mid

    return 0.5 * (low + high)
