"""
Real NYC basketball courts, with their compass orientation derived from public geometry.

NYC Open Data's "Athletic Facilities" dataset (qnem-b8re) carries a `multipolygon` footprint
for every athletic surface the Parks Department maintains - 1,507 of them flagged as
basketball, 536 in Brooklyn. Nobody publishes court *bearing* as a field, but the footprint
makes it computable: fit the tightest rectangle around the polygon and read off the long axis.

That matters because a basketball court is 94 x 50 feet and the baskets sit at the ends of the
LONG axis. So the long axis IS the shooting direction, and the shooting direction is what
decides whether a given day's wind is a headwind, a tailwind, or a crosswind.

No field trip required. (Though measuring a few by hand and checking them against this would
be an excellent way to validate the method - and a much better story than either alone.)

    python3 -m data_pipeline.courts --borough B --limit 20
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
import urllib.parse
import urllib.request

ENDPOINT = "https://data.cityofnewyork.us/resource/qnem-b8re.json"
CACHE = pathlib.Path(__file__).resolve().parent.parent / "data" / "courts"

BOROUGHS = {"B": "Brooklyn", "M": "Manhattan", "Q": "Queens", "X": "Bronx", "R": "Staten Island"}

# Metres per degree near NYC (lat ~40.7). Good to a fraction of a percent over a 30 m court.
METRES_PER_DEG_LAT = 110_540.0
METRES_PER_DEG_LON = 111_320.0 * math.cos(math.radians(40.7))


def fetch_courts(borough: str = "B", limit: int = 1000):
    """Pull basketball-flagged facilities with their geometry. Cached to disk."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"courts_{borough}.json"
    if path.exists():
        return json.loads(path.read_text())

    query = urllib.parse.urlencode({
        "basketball": "true",
        "borough": borough,
        "$limit": limit,
    })
    with urllib.request.urlopen(f"{ENDPOINT}?{query}", timeout=120) as response:
        rows = json.loads(response.read().decode())
    path.write_text(json.dumps(rows))
    return rows


def _to_local_metres(coordinates):
    """Project lon/lat degrees onto a flat local frame in metres: x = east, y = north."""
    lon0 = sum(c[0] for c in coordinates) / len(coordinates)
    lat0 = sum(c[1] for c in coordinates) / len(coordinates)
    return [
        ((lon - lon0) * METRES_PER_DEG_LON, (lat - lat0) * METRES_PER_DEG_LAT)
        for lon, lat in coordinates
    ]


def _convex_hull(points):
    """Andrew's monotone chain. Returns the hull counter-clockwise."""
    points = sorted(set(points))
    if len(points) <= 2:
        return points

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def minimum_area_rectangle(points):
    """
    Tightest enclosing rectangle, by rotating calipers.

    The key theorem: the minimum-area bounding rectangle of a convex polygon always has one
    side flush with one of the polygon's edges. So we only have to try each hull edge, rather
    than every angle - which turns a continuous optimisation into a short loop.

    Returns (long_side_m, short_side_m, bearing_of_long_axis_deg).
    """
    hull = _convex_hull(points)
    if len(hull) < 3:
        return None

    best = None
    for i in range(len(hull)):
        ax, ay = hull[i]
        bx, by = hull[(i + 1) % len(hull)]
        edge_length = math.hypot(bx - ax, by - ay)
        if edge_length < 1e-9:
            continue

        # Unit vector along this edge, and its perpendicular.
        ux, uy = (bx - ax) / edge_length, (by - ay) / edge_length
        px, py = -uy, ux

        along = [x * ux + y * uy for x, y in hull]
        across = [x * px + y * py for x, y in hull]
        width = max(along) - min(along)
        height = max(across) - min(across)
        area = width * height

        if best is None or area < best[0]:
            # Bearing: compass degrees clockwise from north, so atan2(east, north).
            if width >= height:
                long_side, short_side, bearing = width, height, math.degrees(math.atan2(ux, uy))
            else:
                long_side, short_side, bearing = height, width, math.degrees(math.atan2(px, py))
            best = (area, long_side, short_side, bearing % 180.0)

    if best is None:
        return None
    return best[1], best[2], best[3]


def court_geometry(row):
    """
    Extract (length_m, width_m, bearing_deg) from one facility row.

    Bearing is reported modulo 180: a court running north-south is the same court as one
    running south-north, because it has a basket at each end.
    """
    geom = row.get("multipolygon")
    if not geom or geom.get("type") not in ("MultiPolygon", "Polygon"):
        return None

    if geom["type"] == "MultiPolygon":
        rings = [ring for polygon in geom["coordinates"] for ring in polygon]
    else:
        rings = geom["coordinates"]
    if not rings:
        return None

    outer = max(rings, key=len)                 # outer ring = the most detailed one
    if len(outer) < 4:
        return None

    return minimum_area_rectangle(_to_local_metres(outer))


def compass_point(bearing_deg: float) -> str:
    """Nearest compass label for a modulo-180 axis (so N and S are the same axis)."""
    labels = ["N-S", "NNE-SSW", "NE-SW", "ENE-WSW", "E-W", "ESE-WNW", "SE-NW", "SSE-NNW"]
    return labels[int((bearing_deg % 180.0) / 22.5 + 0.5) % 8]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--borough", default="B", choices=sorted(BOROUGHS))
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    rows = fetch_courts(args.borough)
    print(f"{BOROUGHS[args.borough]}: {len(rows)} basketball facilities\n")

    measured = []
    for row in rows:
        geometry = court_geometry(row)
        if geometry is None:
            continue
        length, width, bearing = geometry
        # A regulation full court is 28.7 x 15.2 m; half courts and multi-court slabs vary.
        # Filter to plausible single courts so the orientation statistics mean something.
        if not (15.0 <= length <= 40.0 and 8.0 <= width <= 25.0):
            continue
        measured.append((row, length, width, bearing))

    print(f"{len(measured)} have a plausible single-court footprint\n")
    print(f"{'system':<28}{'len m':>8}{'wid m':>8}{'bearing':>9}  axis")
    print("-" * 64)
    for row, length, width, bearing in measured[:args.limit]:
        print(f"{str(row.get('system'))[:27]:<28}{length:>8.1f}{width:>8.1f}"
              f"{bearing:>8.0f}°  {compass_point(bearing)}")

    if measured:
        print(f"\nOrientation distribution ({len(measured)} courts):")
        buckets = {}
        for _row, _l, _w, bearing in measured:
            buckets[compass_point(bearing)] = buckets.get(compass_point(bearing), 0) + 1
        for axis, count in sorted(buckets.items(), key=lambda kv: -kv[1]):
            bar = "#" * round(40 * count / len(measured))
            print(f"  {axis:<10}{count:>5}  {100*count/len(measured):>5.1f}%  {bar}")

        lengths = sorted(l for _r, l, _w, _b in measured)
        print(f"\nCourt length: median {lengths[len(lengths)//2]:.1f} m "
              f"(regulation full court is 28.7 m)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
