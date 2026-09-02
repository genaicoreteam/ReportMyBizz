"""
core/place_details.py

Pulls the REAL Place Details payload for a resolved place_id.
Every field here comes straight from Google's live API response -- nothing
is invented. If a field is missing from Google's response, we pass through
None / empty and let report_builder.py label it "Not available" rather
than filling in a placeholder value.
"""

FIELDS = [
    "place_id", "name", "rating", "user_ratings_total",
    "formatted_address", "formatted_phone_number",
    "international_phone_number", "website", "url",
    "opening_hours", "business_status", "type",
    "geometry", "photo", "reviews", "editorial_summary",
    "price_level",
]


def get_place_details(place_id: str, gmaps_client) -> dict:
    resp = gmaps_client.place(place_id=place_id, fields=FIELDS)
    result = resp.get("result", {})
    if not result:
        raise ValueError("Google returned no data for this Place ID.")
    return result


def summarize_header(details: dict) -> dict:
    geometry = details.get("geometry", {}).get("location", {})
    return {
        "name": details.get("name", "Unknown business"),
        "rating": details.get("rating"),
        "review_count": details.get("user_ratings_total"),
        "address": details.get("formatted_address"),
        "phone": details.get("formatted_phone_number") or details.get(
            "international_phone_number"),
        "website": details.get("website"),
        "maps_url": details.get("url"),
        "categories": details.get("types", []),
        "business_status": details.get("business_status"),
        "lat": geometry.get("lat"),
        "lng": geometry.get("lng"),
        "has_photos": bool(details.get("photos")),
        "photo_count": len(details.get("photos", [])),
        "description": details.get("editorial_summary", {}).get("overview")
        if details.get("editorial_summary") else None,
        "opening_hours_present": "opening_hours" in details
        and bool(details["opening_hours"].get("weekday_text")),
    }
