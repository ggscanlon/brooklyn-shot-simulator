"""
Tests T5 and T6 - air density.

Air density is the whole reason this project exists: it is the single number through which
temperature, pressure and humidity reach the ball. If it is wrong, every downstream result
is wrong in a way that still *looks* plausible, which is the worst kind of wrong.
"""
import pytest

from physics.atmosphere import air_density, saturation_vapour_pressure

STANDARD_PRESSURE_PA = 101_325.0


class TestT5AirDensityReferenceValues:
    """T5: reproduce textbook dry-air densities to within 0.5%."""

    @pytest.mark.parametrize(
        "temp_c, expected_rho",
        [
            (0.0, 1.2922),    # freezing January morning in Brooklyn
            (15.0, 1.2250),   # ISA standard sea level - the value in every textbook
            (30.0, 1.1644),   # humid July afternoon
        ],
    )
    def test_dry_air_density_matches_reference(self, temp_c, expected_rho):
        rho = air_density(temp_c=temp_c, pressure_pa=STANDARD_PRESSURE_PA, relative_humidity_pct=0.0)
        assert rho == pytest.approx(expected_rho, rel=0.005)

    def test_seasonal_swing_is_about_ten_percent(self):
        """The headline number: how much does a NYC year move air density?"""
        cold = air_density(temp_c=0.0, pressure_pa=STANDARD_PRESSURE_PA, relative_humidity_pct=0.0)
        hot = air_density(temp_c=30.0, pressure_pa=STANDARD_PRESSURE_PA, relative_humidity_pct=0.0)
        swing = (cold - hot) / hot
        assert 0.09 < swing < 0.12


class TestT6HumidityLowersDensity:
    """
    T6: humid air is LESS dense than dry air at the same temperature and pressure.

    This is counter-intuitive to nearly everyone - humid air 'feels heavy'. It is true
    because a water molecule (18 g/mol) is lighter than the N2 (28) and O2 (32) it displaces.
    Getting the sign backwards here is an easy mistake and the test exists to catch it.
    """

    def test_humid_air_is_less_dense_than_dry_air(self):
        dry = air_density(temp_c=25.0, pressure_pa=STANDARD_PRESSURE_PA, relative_humidity_pct=0.0)
        humid = air_density(temp_c=25.0, pressure_pa=STANDARD_PRESSURE_PA, relative_humidity_pct=100.0)
        assert humid < dry

    def test_density_decreases_monotonically_with_humidity(self):
        densities = [
            air_density(temp_c=25.0, pressure_pa=STANDARD_PRESSURE_PA, relative_humidity_pct=rh)
            for rh in (0.0, 25.0, 50.0, 75.0, 100.0)
        ]
        assert densities == sorted(densities, reverse=True)

    def test_humidity_effect_is_small_but_real(self):
        """Humidity matters far less than temperature. Quantify it rather than hand-wave."""
        dry = air_density(temp_c=25.0, pressure_pa=STANDARD_PRESSURE_PA, relative_humidity_pct=0.0)
        humid = air_density(temp_c=25.0, pressure_pa=STANDARD_PRESSURE_PA, relative_humidity_pct=100.0)
        assert 0.001 < (dry - humid) / dry < 0.025


class TestSaturationVapourPressure:
    """Supporting physics for T6, checked against published values."""

    @pytest.mark.parametrize(
        "temp_c, expected_pa",
        [(0.0, 611.2), (20.0, 2339.0), (100.0, 101_325.0)],
    )
    def test_matches_published_values(self, temp_c, expected_pa):
        assert saturation_vapour_pressure(temp_c) == pytest.approx(expected_pa, rel=0.02)

    def test_boiling_point_sanity(self):
        """At 100 C saturation pressure equals atmospheric - that is what boiling means."""
        assert saturation_vapour_pressure(100.0) == pytest.approx(STANDARD_PRESSURE_PA, rel=0.02)
