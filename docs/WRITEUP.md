# Brooklyn Shot Simulator — How It Works and What We Found

*Last verified against code: 2026-09-13*

A physics simulator that answers a specific question: **how much does the weather change a
basketball shot in New York, and what should you do about it?**

This document explains every piece of the code and the mathematics behind it, then summarises
what we have actually learned. It is written to be read top to bottom by someone who has not
seen the code.

---

## Part 1 — The physics

### 1.1 The problem

A basketball in flight is pushed by exactly three things:

1. **Gravity** — constant, downward, boring, and by far the largest.
2. **Drag** — air resistance, opposing motion, growing with the *square* of speed.
3. **The Magnus force** — a sideways push produced by *spin*. This is the one most people
   have never heard of, and it is why a shot with backspin carries further.

Write that as an equation for acceleration (force divided by mass):

```
dv/dt  =  g  -  (rho*Cd*A / 2m) * |v_rel| * v_rel  +  (rho*Cl*A / 2m) * |v_rel| * (w_hat x v_rel)
          ^     ^                                     ^
        gravity  drag                                Magnus
```

where

| symbol | meaning | value for an NBA ball |
|---|---|---|
| `m` | mass | 0.6237 kg |
| `A` | cross-sectional area, `pi*r^2` | 0.044643 m² |
| `r` | radius, from a 0.749 m circumference | 0.11921 m |
| `rho` | **air density** — the weather's only way in | 1.15 – 1.33 kg/m³ |
| `Cd` | drag coefficient | 0.47 |
| `Cl` | lift coefficient, depends on spin | 0 – 0.35 |
| `v_rel` | velocity *relative to the air* = `v_ball - v_wind` | — |
| `w_hat` | unit vector along the spin axis | — |

**The single most important line in this whole project:** weather enters the physics through
`rho`, and nowhere else. Temperature, pressure and humidity are not separate effects on the
ball — they are three inputs to one number. Everything else is bookkeeping.

### 1.2 Why drag goes as v², not v

At the speeds and sizes involved here the ball is shoving air out of the way rather than
sliding through it viscously. In one second it sweeps out a tube of air of volume `A*v`, that
air has mass `rho*A*v`, and it gets pushed to roughly speed `v`. Force is momentum per unit
time, so `F ~ rho*A*v * v = rho*A*v²`. The `Cd/2` out front is the fudge factor that turns
that scaling argument into a real number, and it is measured in a wind tunnel, not derived.

The practical consequence: **doubling the speed quadruples the drag.** Long shots are punished
far more than short ones, which turns out to be the whole story of Part 4.

### 1.3 The Magnus force, and why backspin helps

A spinning ball drags a thin layer of air around with it. On the side turning *into* the
oncoming flow the air is sped up; on the other side it is slowed. Faster air means lower
pressure (Bernoulli), so there is a pressure difference across the ball and it gets pushed
sideways.

The direction is a cross product: `w_hat x v_rel`. Getting that sign wrong makes backspin
push the ball *down* — and the trajectory still looks perfectly plausible, which is what makes
it dangerous. A ball moving `+x` with backspin has an angular-velocity vector along `-y`, and
`(-y) x (+x) = +z` — upward. **Backspin holds the ball up.** That is why shooters are taught it.

How much lift depends on the **spin parameter**:

```
S = omega * r / |v_rel|        (surface speed of the ball / its speed through the air)
Cl = min(Cl_max, k * S)
```

At 3 rev/s, `S ~ 0.26`, giving a lift force around 8% of gravity. Small, but it acts for the
whole flight.

### 1.4 Air density from weather-station numbers

Treat air as dry air plus water vapour, each an ideal gas sharing the total pressure
(Dalton's law):

```
rho = (p - p_v)/(R_d * T)  +  p_v/(R_v * T)
```

with `R_d = 287.058`, `R_v = 461.495` J/(kg·K), `T` in kelvin, and `p_v` the water-vapour
pressure. We get `p_v` from relative humidity times the saturation pressure, using the **Buck
equation**:

```
p_sat(T) = 611.21 * exp( (18.678 - T/234.5) * (T / (257.14 + T)) )     [T in Celsius, result Pa]
```

**Humid air is LESS dense than dry air.** Almost everyone gets this backwards, because humid
air *feels* heavy. It is true because a water molecule (18 g/mol) is lighter than the nitrogen
(28) and oxygen (32) it displaces. The effect is small — about 0.9% from bone-dry to saturated
at 20 °C — so humidity is the weakest of the three weather levers.

### 1.5 Solving it: Runge–Kutta 4

The equation above has no closed-form solution once drag is in it, so we step it forward
numerically. The obvious method — `v += a*dt; r += v*dt` (Euler) — has error proportional to
`dt` and *systematically adds energy*: a ball in a vacuum would slowly climb. RK4 samples the
acceleration four times per step and takes a weighted average:

```
k1 = f(y)                 slope at the start
k2 = f(y + dt/2 * k1)     slope at the midpoint, estimated from k1
k3 = f(y + dt/2 * k2)     midpoint again, refined
k4 = f(y + dt * k3)       slope at the end
y_next = y + dt/6 * (k1 + 2*k2 + 2*k3 + k4)
```

Error falls as `dt⁴`, so at `dt = 1 ms` a one-second flight is accurate to well under a
millimetre. A shot takes ~1,300 steps — nothing for a modern computer.

---

## Part 2 — What each file does

### `physics/ball.py`
Ball constants in one frozen dataclass: mass, circumference, `Cd`, and the lift parameters.
`radius_m` and `area_m2` are derived so they can never disagree with the circumference.
`NBA_BALL` and `WNBA_BALL` are provided.

**In:** nothing. **Out:** constants.

### `physics/atmosphere.py`
- `saturation_vapour_pressure(temp_c) -> Pa` — the Buck equation.
- `air_density(temp_c, pressure_pa, rh_pct) -> kg/m³` — §1.4. The weather's only channel.
- `altimeter_to_station_pressure(inHg, elevation_m) -> Pa` — weather stations report pressure
  *reduced to sea level* so aircraft altimeters agree. That is not the pressure where the ball
  flies. This converts it back.

**In:** three scalars. **Out:** one scalar.

### `physics/trajectory.py`
- `backspin_vector(velocity, rev_per_s)` — builds the angular-velocity vector with the correct
  sign. Returns `[0, -18.85, 0]` rad/s for 3 rev/s of backspin on a shot heading `+x`.
- `simulate(...) -> Trajectory` — the RK4 loop. Takes position, velocity, spin, ball, air
  density, wind. Returns every sampled time, position and velocity. `stop_below_z` ends the
  flight when the ball descends past a height, which is how we ask "where does it cross the
  rim?"
- `horizontal_distance_at_height(traj, z)` — linear interpolation between the two samples
  straddling the crossing. At 1 ms the ball moves ~6 mm per step, over which a parabola is
  straight to about a micron.

Coordinates, everywhere: **x toward the hoop, y to the shooter's left, z up.** Right-handed.
Nearly every sign bug in a project like this traces back to someone forgetting that.

### `physics/solver.py`
`required_launch_speed(...)` answers the *inverse* problem: not "where does this shot land"
but "what shot lands there?" There is no closed form with drag, so it uses **bisection** —
range increases monotonically with launch speed, so halving the interval 40 times converges
to sub-millimetre. Bisection cannot diverge, which matters more than speed here. It raises
rather than returning a confident wrong number if the target is unreachable.

### `data_pipeline/fetch_asos.py`
Downloads hourly observations from the Iowa Environmental Mesonet ASOS archive — free, no API
key, decades of history. Fetches a year at a time with exponential backoff and caches to disk.

One subtlety worth copying elsewhere: the server returns "over capacity" as **HTTP 200 with an
error string in the body**, so checking the status code is not enough. We check that the body
actually looks like data. Caching that error message as if it were observations is the kind of
bug that poisons an analysis weeks later.

### `data_pipeline/climatology.py`
Turns raw text into usable weather.

- `load_observations()` — parses, converts to SI, rejects impossible readings.
- `circular_mean_deg()` — averages compass bearings **as vectors**. Averaging 350° and 10°
  arithmetically gives 180°, which points exactly backwards. This function exists solely to
  prevent that.
- `Observation.wind_vector(court_bearing)` — two traps in one conversion. METAR reports the
  direction wind comes **from**, not toward, so a "270" westerly pushes the ball east — forget
  the 180° flip and every outdoor result reverses. And compass bearings run clockwise from
  north while mathematical angles run anticlockwise from east.
- `MonthlySampler` — see Part 3.

### `analysis/io_trace.py`
Prints the inputs and outputs of every function above with real numbers. Run it after any
physics change and read down the page to see what moved.

### `analysis/shot_selection.py`
The layup-versus-three analysis. See Part 4.

---

## Part 3 — The most important design decision: resample, don't fit

We have 76,961 real hours of Central Park weather (2015–2024). There are two ways to turn that
into "a January day in Brooklyn":

**(A) Fit** a distribution to each variable — a normal for temperature, a Weibull for wind
speed — then draw each independently.

**(B) Resample** — pick one real observed hour out of every January in the record and use all
of its numbers together.

**We chose (B), and the reason is correlation.** Temperature, pressure, wind and humidity are
not independent in the real atmosphere. A cold January hour in New York is disproportionately
a *windy* one, because that is what a nor'easter is. High-pressure days are calm and clear.
Fit four separate distributions and sample them independently and you will cheerfully generate
30 °C with a 1040 hPa high and a 20 m/s gale — weather that has never happened.

Resampling a whole observed hour preserves every correlation for free and assumes nothing
about distributional shape. This matters because the variables have genuinely *different*
shapes: temperature is roughly symmetric, wind speed is strongly right-skewed, and wind
direction is circular and multimodal. No single parametric family covers all four.

The cost: the simulator can never produce an hour more extreme than the worst in the record.
For a basketball game that is a feature.

### The weather we are sampling from

| | Jan | Apr | Jul | Oct |
|---|---|---|---|---|
| temp °C (p10/p50/p90) | -6.1 / 2.2 / 8.9 | 5.6 / 11.1 / 18.3 | 21.7 / 25.6 / 30.0 | 10.0 / 15.6 / 21.1 |
| wind m/s (p50/p90/p99) | 3.1 / 5.1 / 7.9 | 2.6 / 4.6 / 7.2 | 1.5 / 3.1 / 4.6 | 2.1 / 4.1 / 6.2 |
| air density kg/m³ (p50) | 1.278 | 1.234 | 1.172 | 1.219 |

### A known data problem

Central Park reports a usable wind **direction** only **44%** of the time. 21.3% of hours are
genuinely calm; another **34.7% have measurable wind but no direction recorded.** Those are
different things — one is weather, one is an instrument gap — and they must never be added
together into a single "calm" number.

Our runs treat direction-missing hours as calm, which **understates wind**, and does so
unevenly because the gap is seasonal (38% of January hours versus 73% of July hours). So the
results below are biased *optimistic* for outdoor shooting. Fixing this means re-running
against **LGA or JFK**, which are instrumented for aviation and report direction reliably.

---

## Part 4 — Why you should take more layups

### The mechanism

Wind applies a roughly constant sideways acceleration `a`, so the sideways displacement it
causes grows as

```
displacement ~ (1/2) * a * t²
```

Flight time `t` grows with shot distance. So **wind error does not grow linearly as you back
up — it grows with the square of the time you spend in the air.**

| shot | distance | flight time | time² relative to layup |
|---|---|---|---|
| layup | 1.5 m | 0.542 s | 1.0× |
| short 2 | 3.0 m | 0.847 s | 2.4× |
| mid-range | 4.5 m | 1.033 s | 3.6× |
| long 2 | 6.0 m | 1.188 s | 4.8× |
| three | 7.24 m | 1.335 s | **6.1×** |

A three-pointer hangs in the air 2.5× as long as a layup, which means it absorbs roughly **six
times** as much wind displacement. On top of that it accumulates more drag error, because drag
scales with `v²` and a longer shot is thrown harder.

Against this, the scoreboard pulls the other way: a three is worth 50% more. The question is
where those two curves cross — and the answer depends on the month.

### Method

One shot per distance, each calibrated to go in perfectly **indoors**, then fired through 150
real sampled hours per month. All five shots see the **same** weather hours (a paired
comparison) so that any difference between rows is the shot, not the luck of the draw.

### Catastrophe rate — missing by more than 30 cm

| shot | Jan | **Mar** | Jun | Jul | Oct |
|---|---|---|---|---|---|
| layup | 2.0% | 0.7% | 0.0% | 0.0% | 0.0% |
| short 2 | 9.3% | 11.3% | 2.7% | 0.0% | 5.3% |
| mid-range | 25.3% | 40.0% | 8.0% | 2.0% | 18.7% |
| long 2 | 40.7% | 50.0% | 11.3% | 6.0% | 24.7% |
| three | **48.7%** | **58.0%** | 18.7% | 12.7% | 30.7% |

Perfectly monotonic in distance, in every month. **In a Brooklyn March, 58% of three-point
attempts miss by more than 30 cm — and 0.7% of layups do.** That is a factor of 80.

### Expected points per shot (make % × shot value)

| shot | Jan | Mar | Jul | Sep |
|---|---|---|---|---|
| layup | **1.79** | **1.75** | 2.00 | 1.93 |
| short 2 | 1.17 | 0.92 | 1.87 | 1.64 |
| mid-range | 0.85 | 0.69 | 1.63 | 1.56 |
| long 2 | 0.84 | 0.67 | 1.52 | 1.44 |
| three | 1.26 | 0.98 | **2.28** | **2.16** |

**The optimal shot flips with the season. Layups win October through April; threes win May
through September.** In March the layup is worth **+0.77 points per possession** over the
three — roughly the difference between a great offense and a dreadful one.

### An unplanned validation

Look at the long two versus the three. In January both make **42.0%** — identical, because at
those distances the flight times are close. But the three is worth 50% more, and the long two
actually carries a *lower* catastrophe rate only because it is marginally shorter.

**The long two is strictly dominated by the three, in every month.** Same accuracy, less
reward.

Nobody put that in the model. It falls out of drag, Magnus and a scoreboard — and it is
exactly the conclusion the NBA analytics community reached from tracking data over the past
fifteen years, the one that emptied the mid-range out of professional basketball. A physics
simulator that reproduces a known empirical result it was never told about is a simulator
worth some trust.

### What this means for a shooter

- **The reward for backing up grows linearly. The risk grows with the square of flight time.**
  That asymmetry is the whole argument.
- Cold months are dense *and* windy, and both effects push the same way, so winter punishes
  distance twice over.
- The right response to bad weather is not to shoot harder. It is to **shoot from closer**.

---

## Part 5 — What we have learned

### On the physics
1. **Weather reaches the ball through exactly one number**, air density, which ranges from
   about 1.15 (hot July) to 1.33 (cold January) kg/m³ in New York — roughly a **12% swing**.
2. **Backspin genuinely matters.** At 3 rev/s the Magnus force is ~8% of gravity, acting for
   the whole flight.
3. **Humidity is the weakest lever** — about 0.9% of density — and it acts in the direction
   most people guess wrong.
4. **Sensitivity is the real story.** The launch *speed* needed changes only ~0.7% across the
   seasonal density range, yet the *landing point* moves ~9.5 cm. Small input changes amplify
   over a 1.3-second flight, and the make-window is only ±10.9 cm.

### On method — the part worth reading twice
5. **We were wrong twice, publicly, and measuring fixed it.** The first estimate of the
   seasonal effect was off by 5× because it reasoned about the fractional change in the drag
   term instead of integrating it over the flight. The second run was labelled "MEASURED" when
   no observation had entered it.
6. **Hand-picked "typical" values are usually extremes.** Our chosen inputs — 0 °C, 30 °C,
   5 m/s wind — turned out to be roughly p20, p90 and **p90–p99** once real data arrived. That
   inflated every conclusion drawn from them.
7. **Paired comparison matters.** Scoring each shot against its own random weather draw buries
   the comparison in sampling noise. Drawing the weather once and firing every shot through the
   *same* hours removes it entirely.
8. **A median can be an artifact.** Ours jumped tenfold between April and May — not weather,
   but the no-wind fraction crossing 50%, which moved the median from a windy hour to a calm one.
9. **Test the sign, not just the magnitude.** The Magnus cross product is the most likely bug
   in the project, and a wrong sign produces a trajectory that still looks like a basketball
   shot. Only an explicit test catches it.

### On the result
10. **The optimal shot distance depends on the weather.** Layups win October–April, threes win
    May–September. The reward for backing up grows linearly with distance; the risk grows with
    the square of flight time.
11. **The model reproduced a result nobody put into it** — that the long two is strictly
    dominated by the three. That is the real conclusion the NBA analytics community reached
    from a decade of tracking data, and it fell out of drag, Magnus and a scoreboard. It is
    the strongest evidence so far that the simulator is behaving.

### Still open
- Separating temperature from wind. The seasonal swing confounds them — colder months are both
  denser *and* windier — and nothing yet says how the effect splits.
- Re-running on LGA/JFK wind data.
- `data_pipeline/` has no tests, while `physics/` has 25. Both bugs found in the data layer so
  far were found by reading output, which is the wrong way to find bugs.

---

## Running it

```bash
python3 -m data_pipeline.fetch_asos --station NYC --start 2015 --end 2024   # once, ~1 min
python3 -m analysis.io_trace          # what every function takes and returns
python3 -m analysis.shot_selection    # the layup analysis
pytest                                # 25 tests
```
