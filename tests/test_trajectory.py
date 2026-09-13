"""
Tests T1-T4 and T7 - the trajectory integrator.

T1 is the most important test in this project. If you only ever write one test, write T1.
"""
import math

import numpy as np
import pytest

from physics.ball import NBA_BALL
from physics.trajectory import simulate, backspin_vector, horizontal_distance_at_height
from physics.solver import required_launch_speed

GRAVITY = 9.81
NO_SPIN = np.zeros(3)


def launch_velocity(speed, angle_deg):
    """Velocity in the x-z plane: x toward the hoop, z up."""
    a = math.radians(angle_deg)
    return np.array([speed * math.cos(a), 0.0, speed * math.sin(a)])


class TestT1VacuumParabola:
    """
    T1: with no air, the integrator MUST reproduce the closed-form parabola.

    Every sign error, every factor-of-two, every units mistake in the RK4 step shows up here.
    This test is the foundation - if it fails, nothing else is worth debugging.
    """

    def test_matches_closed_form_to_within_one_millimetre(self):
        r0 = np.array([0.0, 0.0, 2.0])
        v0 = launch_velocity(speed=9.0, angle_deg=50.0)

        traj = simulate(
            position=r0, velocity=v0, spin=NO_SPIN,
            ball=NBA_BALL, air_density=0.0, duration=1.2, dt=1e-3,
        )

        for t, actual in zip(traj.times, traj.positions):
            expected = np.array([
                r0[0] + v0[0] * t,
                r0[1] + v0[1] * t,
                r0[2] + v0[2] * t - 0.5 * GRAVITY * t ** 2,
            ])
            assert np.linalg.norm(actual - expected) < 1e-3, f"diverged at t={t:.3f}s"

    def test_vacuum_range_matches_analytic_formula(self):
        """Flat-ground range R = v^2 sin(2*theta) / g, the formula from any physics class."""
        speed, angle = 9.0, 45.0
        traj = simulate(
            position=np.array([0.0, 0.0, 0.0]), velocity=launch_velocity(speed, angle),
            spin=NO_SPIN, ball=NBA_BALL, air_density=0.0, duration=3.0, dt=1e-3,
            stop_below_z=0.0,
        )
        analytic = speed ** 2 * math.sin(2 * math.radians(angle)) / GRAVITY
        assert horizontal_distance_at_height(traj, 0.0) == pytest.approx(analytic, abs=1e-3)


class TestT2TerminalVelocity:
    """T2: a ball dropped with drag converges to sqrt(2mg / (rho*Cd*A))."""

    def test_converges_to_analytic_terminal_velocity(self):
        rho = 1.225
        expected = math.sqrt(
            2 * NBA_BALL.mass_kg * GRAVITY / (rho * NBA_BALL.drag_coefficient * NBA_BALL.area_m2)
        )

        traj = simulate(
            position=np.array([0.0, 0.0, 1000.0]), velocity=np.zeros(3), spin=NO_SPIN,
            ball=NBA_BALL, air_density=rho, duration=60.0, dt=1e-3,
        )

        assert abs(traj.velocities[-1][2]) == pytest.approx(expected, rel=0.01)

    def test_terminal_velocity_is_about_twentytwo_metres_per_second(self):
        """Sanity anchor: a basketball tops out around 22 m/s, roughly 49 mph."""
        rho = 1.225
        v_t = math.sqrt(
            2 * NBA_BALL.mass_kg * GRAVITY / (rho * NBA_BALL.drag_coefficient * NBA_BALL.area_m2)
        )
        assert 20.0 < v_t < 24.0


class TestT3EnergyConservation:
    """T3: no drag, no Magnus, no wind -> total mechanical energy is conserved."""

    def test_energy_conserved_to_within_a_tenth_of_a_percent(self):
        v0 = launch_velocity(speed=9.0, angle_deg=50.0)
        traj = simulate(
            position=np.array([0.0, 0.0, 2.0]), velocity=v0, spin=NO_SPIN,
            ball=NBA_BALL, air_density=0.0, duration=1.5, dt=1e-3,
        )

        m = NBA_BALL.mass_kg
        energies = [
            0.5 * m * float(np.dot(v, v)) + m * GRAVITY * float(r[2])
            for r, v in zip(traj.positions, traj.velocities)
        ]
        drift = (max(energies) - min(energies)) / energies[0]
        assert drift < 1e-3

    def test_drag_strictly_removes_energy(self):
        """With air, energy must decrease monotonically. Drag cannot add energy."""
        v0 = launch_velocity(speed=9.0, angle_deg=50.0)
        traj = simulate(
            position=np.array([0.0, 0.0, 2.0]), velocity=v0, spin=NO_SPIN,
            ball=NBA_BALL, air_density=1.225, duration=1.5, dt=1e-3,
        )
        m = NBA_BALL.mass_kg
        energies = [
            0.5 * m * float(np.dot(v, v)) + m * GRAVITY * float(r[2])
            for r, v in zip(traj.positions, traj.velocities)
        ]
        assert all(b <= a + 1e-9 for a, b in zip(energies, energies[1:]))


class TestT4MagnusDirection:
    """
    T4: backspin must LENGTHEN the shot. Never shorten it.

    This is the single most likely bug in the project. The Magnus term is a cross product,
    and a flipped sign produces a trajectory that still looks like a basketball shot - it
    just quietly gives the wrong answer forever. Hence an explicit test.
    """

    def _range_with_spin(self, rev_per_s):
        v0 = launch_velocity(speed=8.5, angle_deg=48.0)
        spin = backspin_vector(velocity=v0, rev_per_s=rev_per_s)
        traj = simulate(
            position=np.array([0.0, 0.0, 2.0]), velocity=v0, spin=spin,
            ball=NBA_BALL, air_density=1.225, duration=3.0, dt=1e-3, stop_below_z=0.0,
        )
        return horizontal_distance_at_height(traj, 0.0)

    def test_backspin_lengthens_the_shot(self):
        assert self._range_with_spin(3.0) > self._range_with_spin(0.0)

    def test_more_backspin_lengthens_it_further(self):
        ranges = [self._range_with_spin(rev) for rev in (0.0, 1.0, 2.0, 3.0)]
        assert ranges == sorted(ranges)

    def test_topspin_shortens_the_shot(self):
        """The mirror image. Negative rev_per_s is topspin and must drop the ball sooner."""
        assert self._range_with_spin(-3.0) < self._range_with_spin(0.0)

    def test_backspin_vector_points_the_right_way(self):
        """
        Ball moving +x with z up. Backspin means the top of the ball travels backwards (-x),
        which by the right-hand rule is angular velocity along -y.
        """
        v = np.array([8.0, 0.0, 4.0])
        spin = backspin_vector(velocity=v, rev_per_s=3.0)
        assert spin[1] < 0
        assert spin[0] == pytest.approx(0.0, abs=1e-12)
        assert spin[2] == pytest.approx(0.0, abs=1e-12)
        assert np.linalg.norm(spin) == pytest.approx(3.0 * 2 * math.pi, rel=1e-9)


class TestT7DensityMonotonicity:
    """
    T7: denser (colder) air demands a harder shot.

    This is the project's central claim reduced to a single assertion.
    """

    def _speed_needed(self, temp_c):
        from physics.atmosphere import air_density
        rho = air_density(temp_c=temp_c, pressure_pa=101_325.0, relative_humidity_pct=50.0)
        return required_launch_speed(
            horizontal_distance_m=7.24,   # NBA three-point line, top of the arc
            launch_angle_deg=50.0,
            launch_height_m=2.0,
            target_height_m=3.05,         # rim
            ball=NBA_BALL, air_density=rho,
        )

    def test_colder_air_requires_more_launch_speed(self):
        assert self._speed_needed(0.0) > self._speed_needed(30.0)

    def test_requirement_increases_monotonically_as_air_thickens(self):
        speeds = [self._speed_needed(t) for t in (30.0, 20.0, 10.0, 0.0)]
        assert speeds == sorted(speeds)

    def test_the_seasonal_difference_is_small(self):
        """
        Quantifies the headline finding. If this ever fails, the model changed materially
        and the writeup needs revisiting.
        """
        winter, summer = self._speed_needed(0.0), self._speed_needed(30.0)
        assert 0.0 < (winter - summer) / summer < 0.02

    def test_solver_actually_hits_the_target(self):
        """A solver that returns a confident wrong number is worse than one that fails."""
        from physics.atmosphere import air_density
        rho = air_density(temp_c=20.0, pressure_pa=101_325.0, relative_humidity_pct=50.0)
        speed = required_launch_speed(
            horizontal_distance_m=7.24, launch_angle_deg=50.0,
            launch_height_m=2.0, target_height_m=3.05, ball=NBA_BALL, air_density=rho,
        )
        traj = simulate(
            position=np.array([0.0, 0.0, 2.0]), velocity=launch_velocity(speed, 50.0),
            spin=NO_SPIN, ball=NBA_BALL, air_density=rho, duration=4.0, dt=1e-3,
            stop_below_z=3.05,
        )
        assert horizontal_distance_at_height(traj, 3.05) == pytest.approx(7.24, abs=1e-3)
