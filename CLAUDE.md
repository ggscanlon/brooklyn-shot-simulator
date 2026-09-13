# CLAUDE.md — Brooklyn Shot Simulator

## 1. Product

Simulates a basketball shot through real New York air, and compares shooting indoors against
shooting on an outdoor Brooklyn court across the seasons. Ends as a browser game where friends
pick a month, venue and difficulty and shoot.

Primary author is a high-school student learning to program on this project, mentored by Greg.
Target: a college-application passion project. **That makes comprehensibility a functional
requirement, not a nicety** — code he cannot explain in an interview has negative value here.

Spec: `.claude/specs/shot-simulator/requirements.md`. Tier: **Personal-Use-Only**.

## 2. Tech

- **Phase 1 (now): Python.** `numpy` for vectors, `pandas` for weather data, `matplotlib` for
  plots, `pytest` for tests. No framework, no heavy dependencies.
- **Phase 2 (later): C# in Unity**, WebGL build. The physics ports across; test T8 pins the two
  implementations to within 1 mm of each other.
- Python is deliberately not the deployment target. It is where the physics gets figured out.

## 3. Structure

```
physics/       ball.py  atmosphere.py  trajectory.py  solver.py
tests/         test_atmosphere.py  test_trajectory.py
data/          raw ASOS pulls (gitignored) + reduced climatology JSON
notebooks/     exploration
plots/         generated figures (gitignored)
```

`physics/` has no I/O and no network calls. It takes numbers and returns numbers, which is what
makes it testable and what makes the C# port mechanical.

## 4. Constraints

- **Coordinates, everywhere:** x toward the hoop, y to the shooter's left, z up. Right-handed.
  Every sign error in this project traces back to someone forgetting this.
- **SI units internally, always.** Weather data arrives in Fahrenheit, knots and inches of
  mercury; convert once at the boundary and never again.
- **Never modify a test to make it pass.** If a test fails, either the code is wrong or the test
  was written wrong — and if it's the test, fix it and write down why in a comment.
- Physics constants live in exactly one place (`physics/ball.py`, `physics/atmosphere.py`).
  Never inline a magic number at a call site.
- Cd and Cl are borrowed from published sports-ball literature, not measured here. Any writeup
  must say so.
- Wind direction is **circular**. Never take a plain arithmetic mean of it — use vector means.
  Averaging 350 deg and 10 deg the obvious way gives 180 deg, which points exactly backwards.
- Weather data contains `M` (missing) and `T` (trace). Parse defensively.

## 5. Workflow

- Tests first. Watch them fail, then make them pass. The red step is not a formality — it is
  the only proof the test can detect the bug it claims to.
- `pytest` from the project root. The suite takes ~16 s, dominated by the terminal-velocity
  test (60 s of simulated fall) and the bisection solver.
- Git autonomy is **manual** (`.claude/git-auto`) — surface git commands rather than running
  them.
- When a physics change alters a documented result, update §5 of the requirements doc in the
  same change. The measured findings table is a claim; stale claims are worse than none.
