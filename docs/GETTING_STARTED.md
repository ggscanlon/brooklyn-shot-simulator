# Getting Started — setting up GitHub and running the code

Written for someone who has never used GitHub or written code before. Follow it in order.
Nothing here can break anything.

---

## Step 1 — Create your GitHub account

Go to **https://github.com/signup**.

**Pick your username carefully.** This one actually matters. It will appear on every piece of
code you write, and if you put this project on a college application, an admissions officer
may well type it in. `elias-fanith` or `efanith` is right. Something you picked for a game
account at thirteen is not. You can change it later, but links break when you do, so get it
right now.

You will be asked to turn on **two-factor authentication**. GitHub requires it. Use the phone
app option (Authy or Google Authenticator) rather than SMS — it is more secure and easier
once set up. **Save the recovery codes it gives you somewhere that is not your phone.** If you
lose the phone without those codes, the account is gone.

---

## Step 2 — Install the tools

You need two programs: **Git** (tracks changes to code) and **GitHub CLI** (connects your
computer to your account).

**On a Mac** — open Terminal and paste:
```bash
xcode-select --install          # installs git, click through the prompt
brew install gh                 # if you don't have brew: https://brew.sh
```

**On Windows** — download and run both installers, accepting the defaults:
- https://git-scm.com/download/win
- https://cli.github.com

Then open **Git Bash** (it comes with Git) for everything that follows. Not Command Prompt.

**Check it worked** — both commands should print a version number:
```bash
git --version
gh --version
```

---

## Step 3 — Connect your computer to GitHub

```bash
gh auth login
```

Answer: **GitHub.com** → **HTTPS** → **Yes** (authenticate Git) → **Login with a web browser**.
It shows you an eight-character code, you press Enter, your browser opens, you paste the code.

That is the whole authentication setup. You will not have to do it again on this computer.

Now tell Git who you are, so your work is credited to you:
```bash
git config --global user.name "Your Real Name"
git config --global user.email "the-email-you-signed-up-with@example.com"
```

Use your **real name**. Commits are a record of who wrote what, and on this project that
record is the point.

---

## Step 4 — Get the code

```bash
cd ~
git clone https://github.com/ggscanlon/brooklyn-shot-simulator.git
cd brooklyn-shot-simulator
```

You now have every file on your own machine.

---

## Step 5 — Run it

Install the Python libraries the project uses:
```bash
pip install numpy pandas matplotlib pytest
```

Then, in order:

```bash
# Download 10 years of Central Park weather. Takes about a minute. Only needed once.
python3 -m data_pipeline.fetch_asos --station NYC --start 2015 --end 2024

# See what every function takes in and hands back. START HERE - read the output slowly.
python3 -m analysis.io_trace

# The 60 tests. They should all pass.
pytest

# Real Brooklyn courts and which way they face
python3 -m data_pipeline.courts --borough B

# Layups vs threes, by month. Takes ~6 minutes - it runs 9,000 simulated shots.
python3 -m analysis.shot_selection
```

If `python3` is not found on Windows, try `python` instead.

---

## Step 6 — Make it yours

Right now the repo lives on your uncle's account. For a college application it should live on
**yours**, with **your** commits on it. Two ways:

**Option A — he transfers it to you (best).** On the repo page: Settings → scroll to the
bottom → Danger Zone → Transfer ownership → type your username. Everything moves across: the
code, the history, the link. Takes about thirty seconds and you own it afterwards.

**Option B — you fork it.** Click **Fork** at the top right of the repo page. You get your own
copy immediately. GitHub labels it "forked from ggscanlon/..." forever, which is honest but
less clean on an application.

Either way, **the commits you make from here on are yours**, under your name, with dates. That
record is what makes a project credible to someone reading it later.

---

## Step 7 — The everyday loop

Four commands, in this order, every time you change something:

```bash
git status                          # what have I changed?
git add .                           # stage all of it
git commit -m "Describe the change" # save it, with a message
git push                            # send it to GitHub
```

Write commit messages that say **what changed and why**, not "update" or "stuff". Six months
from now, and in an interview, those messages are the story of what you built.

To get changes someone else made:
```bash
git pull
```

---

## If something goes wrong

**"I broke a file and want it back the way it was":**
```bash
git checkout -- path/to/file.py
```

**"I want to see what I changed":**
```bash
git diff
```

**"A test is failing."** Read the error from the *bottom up* — the last few lines say which
test and what it expected. Then find that test in `tests/` and read it. The tests are written
to explain themselves.

**Never delete or weaken a test to make it pass.** If a test fails, either the code is wrong
(fix the code) or the test is wrong (fix the test *and write a comment saying why*). A green
test suite that you got by deleting the red tests is worse than no tests at all — it tells you
everything is fine when it isn't.

---

## What to read first

1. **`docs/WRITEUP.md`** — every equation and what we found. Start here.
2. **`analysis/io_trace.py`** output — the code's inputs and outputs with real numbers.
3. **`physics/trajectory.py`** — the heart of it. Comments explain the *why*, not the what.
4. **`tests/test_trajectory.py`** — read `TestT1VacuumParabola` first. It explains why that
   one test matters more than the rest.

## Good first things to try

- Change `BACKSPIN_REV_S` in `analysis/shot_selection.py` from 3.0 to 0.0 and rerun. How much
  does backspin matter?
- Add your own court to `data_pipeline/courts.py` — find one you actually play on.
- In `physics/ball.py`, switch `NBA_BALL` to `WNBA_BALL`. The ball is lighter and smaller.
  Predict what happens *before* you run it, then check.
- Find the launch angle that makes a three-pointer least sensitive to wind. Nobody has done
  this yet — the angles in the code are reasonable guesses, not optimised.
