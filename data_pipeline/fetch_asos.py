"""
Pull hourly surface observations from the Iowa Environmental Mesonet ASOS archive.

Free, no API key, decades of history. The server rate-limits and sometimes returns
"over capacity", so this fetches one year at a time with backoff and caches each year to
disk. Re-running is cheap: anything already downloaded is skipped.

Run:  python3 -m data_pipeline.fetch_asos --station NYC --start 2015 --end 2024
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

# tmpf  air temperature, F        relh  relative humidity, %
# drct  wind direction, degrees   sknt  wind speed, knots
# alti  altimeter setting, inHg (sea-level reduced - NOT station pressure)
FIELDS = ("tmpf", "relh", "drct", "sknt", "alti")

RAW_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"


def year_url(station: str, year: int) -> str:
    params = [("station", station)]
    params += [("data", f) for f in FIELDS]
    params += [
        ("year1", year), ("month1", 1), ("day1", 1),
        ("year2", year + 1), ("month2", 1), ("day2", 1),
        ("tz", "America/New_York"),
        ("format", "onlycomma"),
        ("latlon", "no"),
        ("missing", "M"),
        ("trace", "T"),
        ("direct", "no"),
        ("report_type", 3),   # 3 = routine hourly METAR, excludes special observations
    ]
    return f"{BASE}?{urllib.parse.urlencode(params)}"


def fetch_year(station: str, year: int, attempts: int = 5, timeout: int = 180) -> pathlib.Path:
    """
    Download one station-year, with exponential backoff.

    The server answers "over capacity" with HTTP 200 and an error string in the body, so a
    status check is not enough - we have to look at the content. Silently caching that error
    string as if it were data is precisely the kind of bug that poisons an analysis weeks later.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{station.lower()}_{year}.csv"

    if path.exists() and path.stat().st_size > 10_000:
        print(f"  {year}: cached ({path.stat().st_size // 1024} KB)")
        return path

    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(year_url(station, year), timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
        except Exception as exc:                      # network flake, timeout, DNS
            body = f"ERROR: {exc}"

        looks_like_data = body.startswith("station,") and body.count("\n") > 100
        if looks_like_data:
            path.write_text(body)
            print(f"  {year}: {body.count(chr(10)):,} rows")
            return path

        wait = min(60, 5 * 2 ** (attempt - 1))
        print(f"  {year}: attempt {attempt}/{attempts} failed "
              f"({body.strip().splitlines()[0][:60] if body.strip() else 'empty'}), "
              f"retrying in {wait}s")
        if attempt < attempts:
            time.sleep(wait)

    raise RuntimeError(f"could not fetch {station} {year} after {attempts} attempts")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", default="NYC", help="NYC=Central Park, LGA, JFK")
    parser.add_argument("--start", type=int, default=2015)
    parser.add_argument("--end", type=int, default=2024)
    args = parser.parse_args()

    print(f"Fetching {args.station} {args.start}-{args.end} -> {RAW_DIR}")
    for year in range(args.start, args.end + 1):
        fetch_year(args.station, year)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
