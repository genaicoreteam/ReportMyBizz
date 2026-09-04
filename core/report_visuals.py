"""
core/report_visuals.py

Translates numbers the pipeline already fetched/computed into the
Good / Average / Poor visual language the PDF uses so it can be read at
a glance instead of studied line by line. No new data is invented here
-- every band is a documented threshold (mirrored in the map's own
color coding) applied to a number computed elsewhere in core/.
"""

from core.chart_renderer import render_ring

# (label, brand-dict key) -- reused everywhere so the map dots, the
# keyword table, and the KPI cards all agree on what "good" means. Each
# key has a matching "<key>_bg" entry in config.REPORT_BRAND for the
# tinted-pill badge look.
_GOOD = ("Good", "good")
_AVERAGE = ("Average", "warn")
_POOR = ("Poor", "danger")


def rank_band(avg_rank):
    if avg_rank is None:
        return _POOR
    if avg_rank <= 5:
        return _GOOD
    if avg_rank <= 10:
        return _AVERAGE
    return _POOR


def pct_band(pct):
    if pct is None:
        return _POOR
    if pct >= 70:
        return _GOOD
    if pct >= 40:
        return _AVERAGE
    return _POOR


def rating_band(rating):
    if rating is None:
        return _POOR
    if rating >= 4.5:
        return _GOOD
    if rating >= 3.5:
        return _AVERAGE
    return _POOR


def reviews_per_week_band(per_week):
    """No verified external "industry average" to compare against, so
    this is our own threshold (documented here, not attributed to any
    outside source) rather than the reference's specific claim."""
    if per_week is None:
        return _POOR
    if per_week >= 1:
        return _GOOD
    if per_week >= 0.3:
        return _AVERAGE
    return _POOR


def build_visuals(geogrid: dict, score: dict, profile_audit: dict,
                   header: dict, reviews: dict, brand: dict) -> dict:
    rank_label, rank_key = rank_band(geogrid["overall_average_rank"])
    score_label, score_key = pct_band(score["overall_score"])
    completion_label, completion_key = pct_band(profile_audit["completion_pct"])
    rating_label, rating_key = rating_band(header["rating"])
    seo_label, seo_key = pct_band(profile_audit["seo_score_pct"])
    reviews_label, reviews_key = reviews_per_week_band(reviews["reviews_per_week_estimate"])

    # Color the keyword table's rank cells with the same scale as the
    # map dots, so a glance at either tells the same story.
    for kw_data in geogrid["by_keyword"].values():
        label, key = rank_band(kw_data["average_rank"])
        kw_data["band_label"] = label
        kw_data["band_color"] = brand[key]
        kw_data["band_bg"] = brand[key + "_bg"]

    return {
        "rank_band_label": rank_label,
        "rank_band_color": brand[rank_key],
        "rank_band_bg": brand[rank_key + "_bg"],
        "score_band_label": score_label,
        "score_band_color": brand[score_key],
        "score_band_bg": brand[score_key + "_bg"],
        "score_ring": render_ring(score["overall_score"], brand[score_key],
                                   track_hex=brand[score_key + "_bg"], text_hex=brand["navy"],
                                   size=168, thickness=19),
        "completion_band_label": completion_label,
        "completion_band_color": brand[completion_key],
        "completion_band_bg": brand[completion_key + "_bg"],
        "completion_ring": render_ring(profile_audit["completion_pct"], brand[completion_key],
                                        track_hex=brand[completion_key + "_bg"], text_hex=brand["navy"],
                                        size=140, thickness=16),
        "rating_band_label": rating_label,
        "rating_band_color": brand[rating_key],
        "rating_band_bg": brand[rating_key + "_bg"],
        "seo_band_label": seo_label,
        "seo_band_color": brand[seo_key],
        "seo_band_bg": brand[seo_key + "_bg"],
        "seo_ring": render_ring(profile_audit["seo_score_pct"], brand[seo_key],
                                 track_hex=brand[seo_key + "_bg"], text_hex=brand["navy"],
                                 size=140, thickness=16),
        "reviews_band_label": reviews_label,
        "reviews_band_color": brand[reviews_key],
        "reviews_band_bg": brand[reviews_key + "_bg"],
        "categories_band_label": _GOOD[0] if profile_audit["additional_categories_count"] > 0 else _POOR[0],
        "categories_band_color": brand["good" if profile_audit["additional_categories_count"] > 0 else "danger"],
        "categories_band_bg": brand["good_bg" if profile_audit["additional_categories_count"] > 0 else "danger_bg"],
    }
