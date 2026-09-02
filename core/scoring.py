"""
core/scoring.py

There is no Google API for a "profile score" -- every tool that shows one
(including the sample report that inspired this project) is applying its
own weighting formula on top of real underlying data. This module does
the same, but the formula is fully documented here (and printed in the
report footer) so nothing is a black box, and every input is a real,
fetched number -- never a placeholder.

Weights (must sum to 100):
  - Rank score        35%  (based on overall average geogrid rank)
  - Rating score       25%  (based on the live Google star rating)
  - Review volume      20%  (based on total review count, log-scaled)
  - Profile completion 20%  (based on profile_auditor.py checklist)
"""

import math

WEIGHTS = {
    "rank": 0.35,
    "rating": 0.25,
    "review_volume": 0.20,
    "completion": 0.20,
}


def _rank_score(avg_rank):
    if avg_rank is None:
        return 0.0
    score = max(0.0, 100 - ((avg_rank - 1) * (100 / 19)))
    return round(min(score, 100), 1)


def _rating_score(rating):
    if rating is None:
        return 0.0
    return round((rating / 5) * 100, 1)


def _review_volume_score(review_count):
    if not review_count:
        return 0.0
    score = min(100, (math.log10(review_count + 1) / math.log10(501)) * 100)
    return round(score, 1)


def compute_score(overall_avg_rank, rating, review_count, completion_pct):
    rank_s = _rank_score(overall_avg_rank)
    rating_s = _rating_score(rating)
    volume_s = _review_volume_score(review_count)
    completion_s = float(completion_pct or 0)

    total = (
        rank_s * WEIGHTS["rank"]
        + rating_s * WEIGHTS["rating"]
        + volume_s * WEIGHTS["review_volume"]
        + completion_s * WEIGHTS["completion"]
    )

    return {
        "overall_score": round(total),
        "components": {
            "rank_score": rank_s,
            "rating_score": rating_s,
            "review_volume_score": volume_s,
            "completion_score": completion_s,
        },
        "weights": WEIGHTS,
    }
