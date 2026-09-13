"""
Air density from the things a weather station actually reports.

This module is the bridge between NOAA data and the physics. Every weather effect in the
whole project reaches the ball through exactly one number: rho, the air density.
"""
import math

# Specific gas constants, J/(kg*K)
R_DRY_AIR = 287.058
R_WATER_VAPOUR = 461.495

KELVIN_OFFSET = 273.15


def saturation_vapour_pressure(temp_c: float) -> float:
    """
    Maximum water-vapour pressure air can hold at this temperature, in pascals.

    Buck equation (1981/1996). Chosen over the simpler Magnus/Tetens form because Tetens
    drifts nearly 3% by 100 C, which would fail our boiling-point sanity check. Buck stays
    within ~0.1% across the whole range we care about and well beyond.
    """
    return 611.21 * math.exp((18.678 - temp_c / 234.5) * (temp_c / (257.14 + temp_c)))


def air_density(temp_c: float, pressure_pa: float, relative_humidity_pct: float) -> float:
    """
    Density of moist air, kg/m^3.

    Treats air as dry air plus water vapour, each an ideal gas, sharing the total pressure
    (Dalton's law):

        rho = (p - p_v)/(R_dry * T)  +  p_v/(R_vapour * T)

    Humid air is LESS dense than dry air at the same temperature and pressure. This surprises
    almost everyone, because humid air *feels* heavy. The reason is that a water molecule
    (18 g/mol) is lighter than the nitrogen (28) and oxygen (32) it displaces, and R_vapour
    being larger than R_dry is that same fact in thermodynamic clothing.
    """
    if not 0.0 <= relative_humidity_pct <= 100.0:
        raise ValueError(f"relative humidity must be 0-100%, got {relative_humidity_pct}")
    if pressure_pa <= 0.0:
        raise ValueError(f"pressure must be positive, got {pressure_pa}")

    temp_k = temp_c + KELVIN_OFFSET
    if temp_k <= 0.0:
        raise ValueError(f"temperature below absolute zero: {temp_c} C")

    vapour_pressure = (relative_humidity_pct / 100.0) * saturation_vapour_pressure(temp_c)
    vapour_pressure = min(vapour_pressure, pressure_pa)  # guard against absurd inputs

    dry_partial_pressure = pressure_pa - vapour_pressure
    return (
        dry_partial_pressure / (R_DRY_AIR * temp_k)
        + vapour_pressure / (R_WATER_VAPOUR * temp_k)
    )


def altimeter_to_station_pressure(altimeter_inhg: float, elevation_m: float) -> float:
    """
    Convert the 'alti' field a weather station reports into actual local pressure, in pascals.

    This matters and is easy to get wrong. Altimeter setting is pressure REDUCED TO SEA LEVEL
    so that aircraft altimeters agree with each other. It is not the pressure where the ball
    is flying. Central Park sits ~10 m up, so the correction is small - but using the wrong
    one is a silent bias, and being able to explain the difference is worth more than the
    fraction of a percent it moves the answer.
    """
    altimeter_pa = altimeter_inhg * 3386.389
    return altimeter_pa * (1.0 - (0.0065 * elevation_m) / 288.15) ** 5.2559
