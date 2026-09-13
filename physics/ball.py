"""Ball properties. Change these numbers and everything downstream changes with them."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Ball:
    """
    A spherical ball in flight.

    drag_coefficient (Cd) and the two lift parameters come from published sports-ball
    measurements, NOT from any wind tunnel of ours. They are the least certain numbers in
    this whole model - say so in the writeup rather than pretending otherwise.
    """
    mass_kg: float
    circumference_m: float
    drag_coefficient: float
    lift_slope: float       # how fast Cl grows with spin parameter S
    lift_max: float         # Cl saturates - a ball cannot generate unlimited lift

    @property
    def radius_m(self) -> float:
        return self.circumference_m / (2.0 * math.pi)

    @property
    def area_m2(self) -> float:
        """Cross-sectional (frontal) area - the disc the air 'sees', not surface area."""
        return math.pi * self.radius_m ** 2


# NBA regulation men's ball: 22 oz, 29.5 inch circumference.
NBA_BALL = Ball(
    mass_kg=0.6237,
    circumference_m=0.749,
    drag_coefficient=0.47,   # smooth-sphere value at the Reynolds numbers of a jump shot
    lift_slope=1.0,
    lift_max=0.35,
)

# A women's/WNBA ball is lighter and smaller - worth simulating as a comparison later.
WNBA_BALL = Ball(
    mass_kg=0.5670,
    circumference_m=0.724,
    drag_coefficient=0.47,
    lift_slope=1.0,
    lift_max=0.35,
)
