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

import time
from config import MAX_RANK_DEPTH, NEARBY_SEARCH_RADIUS_M
from core.grid_utils import haversine_m


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
                 keywords: list, request_delay_sec: float = 0.05):
    keyword_results = {}
    competitor_tally = {}

    for keyword in keywords:
        point_results = []
        found_ranks = []
        for (lat, lng) in grid_points:
            rank, seen_above = rank_at_point(
                gmaps_client, lat, lng, keyword, target_place_id
            )
            point_results.append({"lat": lat, "lng": lng, "rank": rank})
            if rank is not None:
                found_ranks.append(rank)

            for pos, (pid, pname, plat, plng) in enumerate(seen_above, start=1):
                if pid is None:
                    continue
                entry = competitor_tally.setdefault(
                    pid, {"name": pname, "ranks": [], "lat": plat, "lng": plng}
                )
                entry["ranks"].append(pos)

            time.sleep(request_delay_sec)

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
            "name": data["name"],
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
        "competitors": competitors[:5],
    }
