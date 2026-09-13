# Brooklyn Shot Simulator

How much does the weather change a basketball shot in New York — and what should you do
about it?

A physics simulator for basketball trajectories under real New York weather, built on
**76,961 hours** of Central Park observations (2015–2024).

**Headline finding: an identical shot, calibrated indoors, makes ~72% in August and ~37% in
March.** Shot selection should change with the season — see
[`docs/WRITEUP.md`](docs/WRITEUP.md).

---

## What's here

| | |
|---|---|
| [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) | **New to GitHub or code? Start here.** Account setup through running it. |
| [`docs/WRITEUP.md`](docs/WRITEUP.md) | Every equation, every file, and what we learned. |
| `physics/` | The simulator. No I/O, no network — numbers in, numbers out. |
| `data_pipeline/` | Fetches and cleans NOAA/ASOS weather observations. |
| `analysis/` | The studies: I/O trace, shot selection. |
| `tests/` | 60 tests — physics core and weather pipeline. |

## Running it

```bash
pip install numpy pandas matplotlib pytest

python3 -m data_pipeline.fetch_asos --station NYC --start 2015 --end 2024   # once, ~1 min
python3 -m analysis.io_trace          # every function's inputs and outputs, with real numbers
python3 -m analysis.shot_selection    # layups vs threes, by month
pytest                                # 25 tests
```

The raw weather CSVs are not committed — `fetch_asos.py` regenerates them and caches to
`data/raw/`.

## The physics

```
dv/dt = g − (ρ·Cd·A / 2m)·|v_rel|·v_rel + (ρ·Cl·A / 2m)·|v_rel|·(ŵ × v_rel)
        ↑    ↑                             ↑
     gravity drag                        Magnus
```

Integrated with RK4 at 1 ms steps. Weather reaches the ball through exactly one number —
air density ρ — which swings about 12% across a New York year.

## Two things worth knowing before you trust the numbers

**Central Park reports usable wind direction only 44% of the time.** 21.3% of hours are
genuinely calm; another 34.7% have measurable wind with no direction recorded. We treat the
latter as calm, which understates wind — unevenly, since the gap is seasonal. Results are
biased *optimistic* for outdoor shooting. Re-running against LGA or JFK is the fix.

**The temperature/wind decomposition is still open.** Colder months are both denser *and*
windier, and nothing here yet separates the two.

Both are tracked in `.claude/specs/shot-simulator/requirements.md`, along with two earlier
versions of the findings that turned out to be wrong and why.

## Status

Phase 1 (Python: physics + analysis) in progress. Phase 2 — a browser-playable game in
Unity/C# — is planned; test T8 will pin the C# port to the Python reference within 1 mm.
