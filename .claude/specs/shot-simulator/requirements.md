# Requirements — Brooklyn Shot Simulator

**Status:** DRAFT — awaiting approval
**Created:** 2026-09-12
**Tier:** Personal-Use-Only
**Owner:** Greg (mentor) + nephew (primary author, high school, zero prior coding)

---

## 1. Objective

Quantify and then let a player *feel* how much ambient air conditions change a basketball
shot — indoor stadium vs. outdoor Brooklyn court, across the seasons of a New York year.

Two deliverables, in priority order:

1. **The analysis** (Phase 1, Python). A validated trajectory model plus plots that answer:
   *how much does indoor vs. outdoor actually matter, and which variable dominates?*
2. **The game** (Phase 2, Unity/C#). A browser-playable shooting game where friends pick a
   month, a venue and a difficulty, and shoot.

The analysis is the load-bearing deliverable. The game is what makes it fun and shareable.

## 2. Why this scope, in this order

The primary author is learning to program on this project, against a college-application
deadline. Phase 1 is notebooks and math — it produces the substance he can defend in an
interview, and it is where he learns to code. Phase 2 is a guided port of physics he already
understands into C#.

If time runs out, Phase 1 alone is a complete and creditable project. Phase 2 alone would not be.

## 3. The physics model

State: position **r**, velocity **v**, spin **ω** (backspin about the horizontal axis
perpendicular to the shot plane).

```
dv/dt = g
      - (rho*Cd*A / 2m) * |v_rel| * v_rel               drag
      + (rho*Cl*A / 2m) * |v_rel| * (w_hat  x  v_rel)   Magnus
v_rel = v_ball - v_wind
```

- Integrator: **RK4**, fixed dt = 1 ms. Flight time ~1 s, so ~1000 steps — trivially cheap.
- `rho = p / (R_d * T)` with a humidity correction via vapour pressure (moist air is *less*
  dense than dry — a common and instructive intuition failure).
- Ball constants (NBA regulation): m = 0.6237 kg, circumference 0.749 m, r = 0.1192 m,
  A = 0.04464 m^2.
- `Cd ~ 0.47` sphere baseline. `Cl` from spin parameter S = omega*r/|v|; shooters impart
  2-3 rev/s of backspin.
- Constant `g = 9.81 m/s^2`. No Coriolis (absurd at this scale — worth one sentence in the
  writeup explaining why it is negligible).

**Explicitly out of scope for v1:** Reynolds-dependent Cd through the drag crisis, spin decay
during flight, ball deformation. Each is below the noise floor of a human shooter's release
variance, and saying so with a number is better engineering than modelling it.

## 4. Success criteria (the tests that define "done")

Phase 1:

- **T1 Vacuum fallback.** With rho = 0 and omega = 0, the integrator reproduces the closed-form
  parabola to < 1 mm over a 7 m flight. *This is the test that catches sign and scaling errors.*
- **T2 Terminal velocity.** A ball dropped from rest with drag converges to
  sqrt(2mg / (rho*Cd*A)) ~ 21.8 m/s, within 1%.
- **T3 Energy sanity.** With no drag and no Magnus, total energy is conserved to < 0.1% over
  the flight (an RK4 step-size check).
- **T4 Magnus direction.** Backspin must *lengthen* the flight, never shorten it. A sign error
  here is the single most likely bug in the project and is invisible without an explicit test.
- **T5 Air density.** rho(0 C, 101325 Pa) = 1.292 kg/m^3 and rho(30 C) = 1.164, each within 0.5%.
- **T6 Humidity direction.** Raising humidity at fixed T and p must *decrease* rho.
- **T7 Monotonicity.** Colder (denser) air must require more launch speed to travel a fixed
  distance at a fixed angle.

Phase 2:

- **T8 Port fidelity.** For 100 randomised launch conditions, the C# implementation agrees with
  the Python reference to < 1 mm in final position. This is what makes the port trustworthy.
- **T9 Playable.** Loads in a browser, responds to input, reports make/miss, runs at >= 30 fps.

## 5. Findings — three generations, each superseding the last

**Read the labels.** Each block says where its numbers came from. Mixing a chosen scenario
with a sampled result is how an analysis quietly becomes fiction.

### 5a. Pre-simulation estimate (2026-09-12) — SUPERSEDED, kept as a record of method

Back-of-envelope: seasonal density worth ~1-2 cm, 5 m/s crosswind ~25 cm. Wind assumed to
dominate by an order of magnitude. The seasonal figure was wrong by ~5x because it reasoned
about the *fractional* change in the drag term instead of integrating it over the flight.

### 5b. Sensitivity sweep at CHOSEN inputs (2026-09-12) — SUPERSEDED

Ran the physics at hand-picked conditions: 0 C / 30 C, 50% RH, exactly 101325 Pa, 5 m/s wind.
Produced a 9.5 cm seasonal spread and a 68 cm crosswind drift.

**This was mislabelled "MEASURED". It was not.** No observation entered it. Worse, every input
sat near a distribution tail without saying so — once real data arrived, 0 C proved to be about
the 20th percentile of January, 30 C about the 90th of July, and **5 m/s wind roughly a p90-p99
hour**. Extremes on every axis, presented as typical, which inflated the wind-dominance ratio.

### 5c. Monte Carlo over REAL SAMPLED HOURS (2026-09-12) — current

Method: 76,961 real Central Park hours, 2015-2024. Calibrate one shot to go in indoors
(20 C, 40% RH, 9.538 m/s), then fire that identical shot through 400 real hours sampled per
month and record where it lands. Court faces north. Make window +/- 10.9 cm.

| Month | rho p10/p50/p90 | range err cm p10/p50/p90 | make % |
|---|---|---|---|
| Jan | 1.244 / 1.278 / 1.328 | -79.5 / -9.4 / +3.5 | **37.8** |
| Feb | 1.235 / 1.278 / 1.322 | -75.0 / -7.4 / +8.3 | 39.0 |
| Mar | 1.222 / 1.260 / 1.298 | -78.9 / -9.8 / +3.3 | 36.8 |
| Apr | 1.199 / 1.234 / 1.267 | -59.8 / -3.4 / +13.5 | 44.8 |
| May | 1.179 / 1.211 / 1.242 | -45.3 / -1.2 / +2.0 | 62.5 |
| Jun | 1.159 / 1.185 / 1.208 | -23.3 / +0.9 / +8.4 | 65.8 |
| Jul | 1.149 / 1.172 / 1.193 | -13.4 / +1.9 / +8.8 | **70.0** |
| Aug | 1.154 / 1.175 / 1.195 | -11.0 / +1.7 / +5.2 | **72.2** |
| Sep | 1.166 / 1.193 / 1.223 | -39.5 / -0.2 / +2.8 | 61.2 |
| Oct | 1.189 / 1.219 / 1.252 | -38.3 / -1.6 / +2.0 | 64.2 |
| Nov | 1.210 / 1.249 / 1.283 | -52.7 / -4.3 / +1.3 | 57.0 |
| Dec | 1.230 / 1.267 / 1.307 | -55.1 / -6.7 / +0.6 | 42.2 |

**The headline: an indoor-calibrated shot makes ~72% in August and ~37% in March.** Roughly a
two-fold swing across a NYC year, from a shooter who did nothing different. That is a far
stronger result than either earlier version, and it is the one the game should be built around.

Note the p10 column. Those are the windy tail: a January hour at p10 lands the ball **80 cm
short**. The median January miss is only -9.4 cm. Outdoor shooting is not uniformly harder —
it is *occasionally catastrophic*, and the tail is the story.

### 5d. KNOWN BIAS in 5c — must be fixed before this is quotable

Central Park reports a usable wind direction only **44%** of the time: 21.3% of hours are
genuinely calm, but **34.7% have measurable wind with no direction recorded**. The 5c run
treats direction-missing hours as calm, which *understates wind* — and does so unevenly,
because the gap is seasonal (38% of January hours vs 73% of July hours get no wind applied).

The artifact is visible in the data. Median |miss| jumps from 25.5 cm in April to 2.2 cm in
May, exactly where the no-wind fraction crosses 50% (47.6% -> 64.5%). That is the median
stepping across the calm threshold, not the weather changing. **Any median-based statistic in
5c is therefore suspect; the make-% and percentile columns are sounder but still biased toward
optimism.**

Fix: re-run against **LGA or JFK**, which are instrumented for aviation and report direction
far more reliably. KNYC is a sheltered park site with a known-poor wind record. Until then,
5c understates outdoor difficulty, and the true seasonal swing is probably wider than 37-72%.

### 5e. Still owed

A decomposition run separating temperature from wind. 5c confounds them — colder months are
both denser *and* windier, and nothing above says how the 2x swing splits between the two.
That is the actual question the project set out to answer.

## 6. Data

**Source:** Iowa Environmental Mesonet ASOS archive. Free, no API key, decades of history.
Verified working 2026-09-12 against station NYC (Central Park).

Fields: `tmpf` (temp F), `relh` (RH %), `drct` (wind dir deg), `sknt` (wind kt), `alti` (inHg).

Stations: **NYC** (Central Park), **LGA**, **JFK**.

**Two modes, both required:**
- **Baked climatology** — fetch ~10 years once, reduce to per-month p10/p50/p90 distributions,
  ship as JSON. Drives the game. Offline, reproducible, demo-safe.
- **Live lookup** — optional "shoot in today's weather" via Open-Meteo (free, no key).

### Known data hazards (must be handled, not discovered later)
- `M` (missing) appears in any column — observed in `drct` during calm winds.
- `T` means trace precipitation, not a number.
- Calm wind gives direction 0 *and* speed 0; direction is meaningless, not north.
- Wind direction is a **circular** quantity. Averaging 350 deg and 10 deg naively yields 180 deg,
  which is exactly backwards. Use vector means.
- Units are imperial throughout and must be converted exactly once, at the boundary.
- Altimeter setting is **not** station pressure; it is reduced to sea level. Converting it
  properly matters for air density and is a genuine physics detail worth getting right.

## 7. Game design (Phase 2)

- **Venues:** indoor stadium (still air, ~20 C, controlled) vs. named Brooklyn outdoor courts.
  Court orientation differs, so prevailing wind hits each differently.
- **Inputs:** month, venue, difficulty.
- **Difficulty** scales *release variance*, not physics — a harder setting means a less
  consistent shooter, which is both realistic and the honest way to make a physics sim harder.
- **Feedback:** show the trajectory, the air density in use, and the wind vector, so the player
  sees *why* a shot drifted.

## 8. Limitations (stated, not discovered)

- Models a ball in flight, not a human. Release variance is a fitted parameter, not derived.
- Cd and Cl for a basketball come from published sphere/sports-ball data, not from our own wind
  tunnel. Cite the sources; do not present them as measured here.
- Indoor conditions are assumed, not observed — no public feed for stadium interior air.
- A real court has people, rims with varying stiffness, and wet spots. None are modelled.

## 9. Milestones

| # | Deliverable | Gate |
|---|---|---|
| M1 | Physics core + tests T1-T7 green | The parabola test passes |
| M2 | Weather pipeline + climatology JSON | Handles all Section 6 hazards |
| M3 | Analysis notebook + plots | The wind-vs-temperature comparison plot exists |
| M4 | **Writeup** | *Project is creditable from here even if M5-M6 never land* |
| M5 | Unity port + T8 fidelity test | C# matches Python to < 1 mm |
| M6 | Playable web build + rim/backboard collisions | Friends can click a link |

Collisions are deliberately sequenced last: they are the best *game* feature and the most
likely to consume the remaining time.

## 10. Open questions

- Which Brooklyn courts? (Needs the nephew's input — this is his half of the design.)
- Does he want a science-fair entry as an intermediate deadline?
- Interview timing: applications are due Nov 1, but interviews often run Dec-Feb, which may
  give M5-M6 more runway than the application deadline suggests.
