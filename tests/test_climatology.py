"""
Tests for the weather pipeline.

Every bug found in this module so far was found by squinting at printed output, which is the
wrong way to find bugs. These tests pin the traps that actually bit us.
"""
import math
import random

import pytest

from data_pipeline.climatology import (
    Observation, circular_mean_deg, percentile, _number, KNOTS_TO_MS,
)


def obs(speed_ms=5.0, from_deg=270.0, month=1):
    return Observation(
        month=month, temp_c=10.0, pressure_pa=101_000.0,
        relative_humidity_pct=50.0, wind_speed_ms=speed_ms, wind_from_deg=from_deg,
    )


class TestCircularMean:
    """The 350/10 problem. A plain arithmetic mean is off by 180 degrees."""

    def test_wraparound_does_not_point_backwards(self):
        assert circular_mean_deg([350.0, 10.0]) == pytest.approx(0.0, abs=1e-6)

    def test_does_not_return_360(self):
        """360 is numerically correct but reads as a bug. Normalise it."""
        assert circular_mean_deg([350.0, 10.0]) < 1e-6

    def test_agrees_with_naive_mean_when_there_is_no_wraparound(self):
        assert circular_mean_deg([270.0, 280.0, 290.0]) == pytest.approx(280.0, abs=1e-6)

    def test_quadrant(self):
        assert circular_mean_deg([0.0, 90.0]) == pytest.approx(45.0, abs=1e-6)

    def test_ignores_missing(self):
        assert circular_mean_deg([90.0, None, 90.0]) == pytest.approx(90.0, abs=1e-6)

    def test_opposed_directions_have_no_mean(self):
        """North and south average to nothing. Returning 0 or 180 would both be lies."""
        assert circular_mean_deg([0.0, 180.0]) is None

    def test_empty_is_none(self):
        assert circular_mean_deg([]) is None
        assert circular_mean_deg([None, None]) is None


class TestFieldParsing:
    """ASOS text carries sentinels that must never become numbers."""

    @pytest.mark.parametrize("raw", ["M", "T", "", "   ", "null", "None", "garbage"])
    def test_sentinels_become_none_not_zero(self, raw):
        """A silent zero is a wrong measurement in disguise - due north, or absolute calm."""
        assert _number(raw) is None

    @pytest.mark.parametrize("raw, expected", [("29.92", 29.92), ("-5", -5.0), (" 3.0 ", 3.0)])
    def test_real_numbers_parse(self, raw, expected):
        assert _number(raw) == pytest.approx(expected)


class TestVariableWind:
    """
    The VRB rule. METAR reports a variable direction ONLY at 6 knots or less, and the feed
    renders it as a null. Our own data shows the cliff exactly at 7 knots.
    """

    def test_calm_is_not_variable(self):
        assert obs(speed_ms=0.0, from_deg=None).wind_is_variable is False

    def test_wind_without_direction_is_variable(self):
        assert obs(speed_ms=2.0, from_deg=None).wind_is_variable is True

    def test_wind_with_direction_is_not_variable(self):
        assert obs(speed_ms=2.0, from_deg=180.0).wind_is_variable is False

    def test_calm_produces_no_wind_regardless_of_rng(self):
        assert obs(speed_ms=0.0, from_deg=None).wind_vector(rng=random.Random(1)) == (0.0, 0.0, 0.0)

    def test_variable_hour_without_rng_is_zero_and_that_is_the_documented_default(self):
        assert obs(speed_ms=3.0, from_deg=None).wind_vector() == (0.0, 0.0, 0.0)

    def test_variable_hour_with_rng_keeps_the_observed_speed(self):
        """
        The whole point. A variable hour still has real wind in it, and deleting that wind is
        what biased the original analysis.
        """
        down, cross, _ = obs(speed_ms=3.0, from_deg=None).wind_vector(rng=random.Random(7))
        assert math.hypot(down, cross) == pytest.approx(3.0, rel=1e-9)

    def test_variable_directions_are_uniform_not_prevailing(self):
        """
        'Variable' means no prevailing direction, so the draws must spread over the compass.
        If this ever concentrates, someone has swapped in the observed-direction distribution,
        which would be the wrong population.
        """
        rng = random.Random(20260913)
        sample = obs(speed_ms=3.0, from_deg=None)
        quadrants = [0, 0, 0, 0]
        for _ in range(4000):
            down, cross, _ = sample.wind_vector(rng=rng)
            angle = math.degrees(math.atan2(cross, down)) % 360.0
            quadrants[int(angle // 90)] += 1
        for count in quadrants:
            assert 850 < count < 1150, f"not uniform: {quadrants}"


class TestWindVectorGeometry:
    """Direction conventions. Each of these silently reverses results when wrong."""

    def test_wind_reported_FROM_the_west_pushes_the_ball_east(self):
        """METAR reports where wind comes FROM. Forgetting the flip reverses every result."""
        down, cross, _ = obs(speed_ms=6.0, from_deg=270.0).wind_vector(court_bearing_deg=90.0)
        assert down == pytest.approx(6.0, abs=1e-9)      # shooting east = tailwind

    def test_same_wind_is_a_headwind_shooting_the_other_way(self):
        down, _, _ = obs(speed_ms=6.0, from_deg=270.0).wind_vector(court_bearing_deg=270.0)
        assert down == pytest.approx(-6.0, abs=1e-9)

    def test_same_wind_is_pure_crosswind_shooting_north(self):
        down, cross, _ = obs(speed_ms=6.0, from_deg=270.0).wind_vector(court_bearing_deg=0.0)
        assert down == pytest.approx(0.0, abs=1e-9)
        assert abs(cross) == pytest.approx(6.0, abs=1e-9)

    def test_speed_is_preserved_at_every_court_bearing(self):
        for bearing in range(0, 360, 15):
            down, cross, _ = obs(speed_ms=4.0, from_deg=35.0).wind_vector(bearing)
            assert math.hypot(down, cross) == pytest.approx(4.0, rel=1e-9)

    def test_vertical_component_is_always_zero(self):
        """We model horizontal wind only. Updraughts on a Brooklyn court are out of scope."""
        assert obs().wind_vector(45.0)[2] == 0.0


class TestUnitConversion:
    def test_knots_to_ms(self):
        assert 10 * KNOTS_TO_MS == pytest.approx(5.14444, rel=1e-5)

    def test_six_knots_is_the_vrb_ceiling(self):
        """The threshold the whole variable-wind story rests on."""
        assert 6 * KNOTS_TO_MS == pytest.approx(3.087, abs=0.001)
        assert 7 * KNOTS_TO_MS == pytest.approx(3.601, abs=0.001)


class TestPercentile:
    def test_endpoints(self):
        assert percentile([1, 2, 3, 4, 5], 0) == 1
        assert percentile([1, 2, 3, 4, 5], 100) == 5

    def test_median(self):
        assert percentile([1, 2, 3, 4, 5], 50) == 3

    def test_interpolates(self):
        assert percentile([0, 10], 25) == pytest.approx(2.5)

    def test_unsorted_input(self):
        assert percentile([5, 1, 3], 50) == 3
