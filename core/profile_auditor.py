"""
core/profile_auditor.py

Builds a completeness checklist purely from fields Google's public Places
API actually returns. Anything Google's public API cannot see at all
(e.g. the owner-entered "Services" list, "Products" catalog, or the exact
count of categories beyond the primary type) is marked as "Not visible
via public API" rather than guessed as pass/fail.
"""

# Google's own generic labels, not real business categories -- excluded
# so "additional categories" only counts types that actually say
# something about the business (mirrors rank_tracker.derive_keywords).
_GENERIC_TYPES = {"point_of_interest", "establishment", "premise", "geocode", "store"}


def audit_profile(details: dict, header: dict) -> dict:
    checklist = []

    def item(label, status, note=None):
        checklist.append({"label": label, "status": status, "note": note})

    item("Business Name", "complete" if details.get("name") else "incomplete")
    item("Primary Category",
         "complete" if details.get("types") else "incomplete")
    item("Address", "complete" if details.get("formatted_address") else "incomplete")
    item("Phone Number",
         "complete" if (details.get("formatted_phone_number")
                         or details.get("international_phone_number"))
         else "incomplete")
    item("Website", "complete" if details.get("website") else "incomplete")
    item("Business Hours",
         "complete" if header.get("opening_hours_present") else "incomplete")
    item("Photos",
         "complete" if header.get("has_photos") else "incomplete",
         note=f"{header.get('photo_count', 0)} photos indexed publicly")
    item("Business Description",
         "complete" if header.get("description") else "incomplete",
         note=None if header.get("description") else
         "Google did not return a public editorial description; the "
         "owner may still have one set privately.")

    unavailable = [
        {"label": "Services / Products List",
         "note": "Not visible via public API. Only visible on the live "
                  "Maps listing page or to the profile owner."},
        {"label": "Additional Categories (exact count)",
         "note": "Public API only exposes Google's generic place `types`, "
                  "not the owner-curated category list shown in GBP dashboard."},
        {"label": "Q&A / Booking Links",
         "note": "Not exposed by the public Places API."},
    ]

    complete_count = sum(1 for c in checklist if c["status"] == "complete")
    completion_pct = round((complete_count / len(checklist)) * 100)

    # Real (if imperfect) proxy for "additional categories": Google's
    # `types` array minus its own generic labels and the primary type.
    # It won't exactly match the owner-curated category list in the GBP
    # dashboard (unavailable[1] above still says so), but it's actual
    # API data, not a placeholder.
    types = [t for t in (details.get("types") or []) if t not in _GENERIC_TYPES]
    additional_categories_count = max(0, len(types) - 1)

    seo_checks = [
        ("Primary Category", bool(details.get("types"))),
        ("Additional Category", additional_categories_count > 0),
        ("Business Description", bool(header.get("description"))),
        ("Website", bool(details.get("website"))),
    ]
    seo_missing = [label for label, ok in seo_checks if not ok]
    seo_score_pct = round(sum(ok for _, ok in seo_checks) / len(seo_checks) * 100)

    return {
        "checklist": checklist,
        "unavailable": unavailable,
        "completion_pct": completion_pct,
        "complete_count": complete_count,
        "total_checked": len(checklist),
        "additional_categories_count": additional_categories_count,
        "seo_score_pct": seo_score_pct,
        "seo_missing": seo_missing,
    }
