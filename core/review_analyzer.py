"""
core/review_analyzer.py

Google's public Places API exposes at most the 5 most recent reviews for
any business, and -- critically -- it does NOT expose whether the owner
replied to a review. That field only exists in the Google Business Profile
API, which requires the profile OWNER to authenticate.

So, honestly:
  - "reviews_per_week_estimate" IS real, computed from the actual reviews
    Google returns (clearly labeled as a small sample, not full history).
  - "response_rate" is explicitly marked unavailable. We never invent a
    percentage for it.
"""

from datetime import datetime


def analyze_reviews(details: dict) -> dict:
    reviews = details.get("reviews", []) or []

    if not reviews:
        return {
            "sample_size": 0,
            "reviews": [],
            "reviews_per_week_estimate": None,
            "reviews_per_week_note": "No public reviews returned by Google to estimate from.",
            "response_rate": None,
            "response_rate_note": "Not available via public API (requires "
                                   "Business Profile owner access).",
        }

    timestamps = sorted(r.get("time") for r in reviews if r.get("time"))
    per_week = None
    if len(timestamps) >= 2:
        span_seconds = timestamps[-1] - timestamps[0]
        span_weeks = max(span_seconds / (7 * 24 * 3600), 1 / 7)
        per_week = round(len(timestamps) / span_weeks, 2)

    formatted = []
    for r in reviews:
        ts = r.get("time")
        formatted.append({
            "author": r.get("author_name"),
            "rating": r.get("rating"),
            "text": (r.get("text") or "")[:200],
            "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else None,
        })

    return {
        "sample_size": len(reviews),
        "reviews": formatted,
        "reviews_per_week_estimate": per_week,
        "reviews_per_week_note": "Estimated from the last "
                                  f"{len(reviews)} public reviews only "
                                  "(Google's public API does not expose "
                                  "full review history).",
        "response_rate": None,
        "response_rate_note": "Not available via public API (requires "
                               "Business Profile owner access).",
    }
