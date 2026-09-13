"""Does the model support the spec's hypothesis? Tune a shot indoors, then change one thing."""
import numpy as np
from physics.ball import NBA_BALL
from physics.atmosphere import air_density
from physics.solver import required_launch_speed
from physics.trajectory import simulate, backspin_vector, horizontal_distance_at_height

P, THREE, RIM, RELEASE, ANGLE, SPIN = 101_325.0, 7.24, 3.05, 2.0, 50.0, 3.0
indoor = air_density(temp_c=20.0, pressure_pa=P, relative_humidity_pct=40.0)

speed = required_launch_speed(THREE, ANGLE, RELEASE, RIM, NBA_BALL, indoor, spin_rev_per_s=SPIN)
print(f"Indoor (20C): release {speed:.4f} m/s, rho={indoor:.4f}\n")

def shot(rho, wind=None):
    a = np.radians(ANGLE)
    v = np.array([speed*np.cos(a), 0.0, speed*np.sin(a)])
    traj = simulate(np.array([0.,0.,RELEASE]), v, backspin_vector(v, SPIN), NBA_BALL, rho,
                    duration=8.0, dt=1e-3, wind=wind, stop_below_z=RIM)
    d = horizontal_distance_at_height(traj, RIM)
    # lateral drift at the crossing
    lat = 0.0
    for i in range(len(traj.positions)-1):
        zh, zn = traj.positions[i][2], traj.positions[i+1][2]
        if zn < zh and zh >= RIM > zn:
            f = (zh-RIM)/(zh-zn)
            lat = float(traj.positions[i][1] + f*(traj.positions[i+1][1]-traj.positions[i][1]))
            break
    return d, lat

base, _ = shot(indoor)
print(f"{'condition':<34}{'range err':>12}{'lateral':>12}")
print("-"*58)
for label, rho, wind in [
    ("Outdoor  0C (winter)", air_density(0.0, P, 50.0), None),
    ("Outdoor 30C (summer)", air_density(30.0, P, 50.0), None),
    ("Outdoor 20C, 5 m/s crosswind", indoor, np.array([0.,5.,0.])),
    ("Outdoor 20C, 5 m/s headwind",  indoor, np.array([-5.,0.,0.])),
    ("Outdoor 20C, 2 m/s crosswind", indoor, np.array([0.,2.,0.])),
]:
    d, lat = shot(rho, wind)
    print(f"{label:<34}{(d-base)*100:>+10.2f}cm{lat*100:>+10.2f}cm")
print(f"\nMargin for error: rim 45.7cm - ball 23.9cm => +/- {(0.457-0.239)/2*100:.1f}cm")
