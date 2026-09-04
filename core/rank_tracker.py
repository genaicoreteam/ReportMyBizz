"""
core/rank_tracker.py

Runs REAL Google Places "Nearby Search" calls from every grid point, for
every keyword, and records the target business's actual position in each
result set. This mirrors what paid geogrid tools (LocalFalcon, Grexa,
DataForSEO) do -- we're just calling Google's own developer API instead of
a third-party SERP scraper, which keeps this on the free tier.

Honesty note: Google's Places API ranking is not guaranteed to be pixel
identical to the consumer Local Pack a human sees, since Google doesn't
expose that exact algorithm publicly. We do NOT fabricate or smooth the
numbers -- whatever position Google's API returns is what gets reported.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from config import MAX_RANK_DEPTH, NEARBY_SEARCH_RADIUS_M
from core.grid_utils import haversine_m

# Every (keyword, grid point) pair is one independent Nearby Search call --
# a default 5x5 grid x 5 keywords is 125 of them. Run sequentially (as this
# used to) that took over two minutes end to end, well past what a browser
# or a serverless function's request timeout tolerates. They're fanned out
# across a small thread pool instead: googlemaps.Client self-throttles to
# ~60 queries/second internally regardless of caller thread count, so this
# doesn't risk hammering Google -- it just stops leaving the CPU idle while
# each call waits on network I/O.
MAX_WORKERS = 15

# Real Places listings often stuff extra keywords into the business name
# itself, separated by "|" or "-" (a common local-SEO practice) -- e.g.
# "Dr. X | General Physician & Diabetologist | Some Clinic". Left as-is,
# a single competitor row can wrap 4-5 lines and blow the report's
# two-column layout out to nearly a full page by itself, which is what
# forces every section after it onto its own mostly-empty page. The
# report only needs enough of the name to identify the business, not
# the owner's full keyword-stuffed string -- so this trims to the
# leading clean segment (and a hard character cap besides) purely for
# display; nothing about the real ranking data changes.
_NAME_MAX_LEN = 42


def _clean_competitor_name(name: str) -> str:
    for sep in (" | ", " – ", " -- ", " - "):
        if sep in name:
            name = name.split(sep)[0].strip()
            break
    if len(name) > _NAME_MAX_LEN:
        name = name[:_NAME_MAX_LEN - 1].rstrip() + "…"
    return name


def derive_keywords(categories: list, max_keywords: int) -> list:
    GENERIC = {
        "point_of_interest", "establishment", "premise",
        "geocode", "store",
    }
    cleaned = []
    for t in categories:
        if t in GENERIC:
            continue
        cleaned.append(t.replace("_", " "))
    seen = set()
    keywords = []
    for k in cleaned:
        if k not in seen:
            seen.add(k)
            keywords.append(k)
    return keywords[:max_keywords] if keywords else ["business"]


def rank_at_point(gmaps_client, lat: float, lng: float, keyword: str,
                   target_place_id: str):
    """Ranks are computed only among results Google actually placed
    within the search radius. Google's Nearby Search API is documented
    to use `radius` as a bias, not a hard cutoff -- when very few local
    matches exist for a niche keyword it can quietly widen the search
    and return places from a neighboring city or town. Left unfiltered,
    that shows up as a "local competitor" that's actually 100km away, so
    every result is re-checked against the real distance from the
    search point before it counts toward rank or the competitor list.
    """
    results = gmaps_client.places_nearby(
        location=(lat, lng),
        radius=NEARBY_SEARCH_RADIUS_M,
        keyword=keyword,
    )
    raw_places = results.get("results", [])

    local_places = []
    for place in raw_places:
        loc = place.get("geometry", {}).get("location", {})
        plat, plng = loc.get("lat"), loc.get("lng")
        if plat is None or plng is None:
            continue
        if haversine_m(lat, lng, plat, plng) <= NEARBY_SEARCH_RADIUS_M:
            local_places.append((place, plat, plng))

    places = local_places[:MAX_RANK_DEPTH]

    seen_above = []
    for idx, (place, plat, plng) in enumerate(places, start=1):
        pid = place.get("place_id")
        if pid == target_place_id:
            return idx, seen_above
        seen_above.append((pid, place.get("name"), plat, plng))
    return None, seen_above


def run_geogrid(gmaps_client, target_place_id: str, grid_points: list,
                 keywords: list, max_workers: int = MAX_WORKERS):
    competitor_tally = {}

    # Slots to fill in as results come back -- concurrent completion order
    # is unpredictable, so each job carries its own point index home with it
    # rather than relying on append order.
    points_by_keyword = {kw: [None] * len(grid_points) for kw in keywords}

    jobs = [
        (keyword, point_idx, lat, lng)
        for keyword in keywords
        for point_idx, (lat, lng) in enumerate(grid_points)
    ]

    def _run(job):
        keyword, point_idx, lat, lng = job
        rank, seen_above = rank_at_point(gmaps_client, lat, lng, keyword, target_place_id)
        return keyword, point_idx, lat, lng, rank, seen_above

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_run, job) for job in jobs]
        # Results are only ever written to shared state (points_by_keyword,
        # competitor_tally) here in the main thread as each future resolves,
        # never inside a worker -- so no locking is needed despite the
        # concurrency above.
        for future in as_completed(futures):
            keyword, point_idx, lat, lng, rank, seen_above = future.result()
            points_by_keyword[keyword][point_idx] = {"lat": lat, "lng": lng, "rank": rank}

            for pos, (pid, pname, plat, plng) in enumerate(seen_above, start=1):
                if pid is None:
                    continue
                entry = competitor_tally.setdefault(
                    pid, {"name": pname, "ranks": [], "lat": plat, "lng": plng}
                )
                entry["ranks"].append(pos)

    keyword_results = {}
    for keyword in keywords:
        point_results = points_by_keyword[keyword]
        found_ranks = [p["rank"] for p in point_results if p["rank"] is not None]
        avg_rank = round(sum(found_ranks) / len(found_ranks), 1) if found_ranks else None
        keyword_results[keyword] = {
            "points": point_results,
            "average_rank": avg_rank,
            "found_count": len(found_ranks),
            "total_points": len(grid_points),
        }

    competitors = []
    for pid, data in competitor_tally.items():
        avg = round(sum(data["ranks"]) / len(data["ranks"]), 1)
        competitors.append({
            "place_id": pid,
            "name": _clean_competitor_name(data["name"]),
            "average_rank": avg,
            "appearances": len(data["ranks"]),
            "lat": data["lat"],
            "lng": data["lng"],
        })
    competitors.sort(key=lambda c: c["average_rank"])

    overall_ranks = [
        kr["average_rank"] for kr in keyword_results.values()
        if kr["average_rank"] is not None
    ]
    overall_average = round(sum(overall_ranks) / len(overall_ranks), 1) if overall_ranks else None

    return {
        "by_keyword": keyword_results,
        "overall_average_rank": overall_average,
        # Capped to match the top 3 pins actually numbered on the grid
        # maps below (report_builder.py's map_competitors) -- showing
        # more here than get a "#N" badge on the map reads as
        # inconsistent, and a long tail of extra rows was also the
        # single biggest driver of the report's page count/whitespace.
        "competitors": competitors[:3],
    }
