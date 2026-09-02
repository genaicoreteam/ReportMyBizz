"""
core/place_resolver.py

Takes whatever the user pastes in -- a full Google Maps / Business Profile
URL, a shortened maps.app.goo.gl link, a raw CID, or a raw Place ID -- and
resolves it to a canonical Google `place_id`.

No fabricated data: if resolution fails, we raise a clear error instead of
guessing.
"""

import re
import requests
import googlemaps


class PlaceResolutionError(Exception):
    pass


def _expand_short_link(url: str) -> str:
    try:
        resp = requests.get(url, allow_redirects=True, timeout=10)
        return resp.url
    except requests.RequestException as exc:
        raise PlaceResolutionError(f"Could not follow link redirect: {exc}")


def _extract_cid(url: str):
    m = re.search(r"[?&]cid=(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"0x[0-9a-fA-F]+:0x([0-9a-fA-F]+)", url)
    if m:
        return str(int(m.group(1), 16))
    return None


def _extract_name_and_area(url: str):
    from urllib.parse import unquote, urlparse, parse_qs

    # Strategy 1: classic /maps/place/<Business+Name>/... URL
    m = re.search(r"/maps/place/([^/@]+)", url)
    if m:
        return unquote(m.group(1).replace("+", " "))

    # Strategy 2: some short links (e.g. share.google) resolve to a Google
    # Search / Knowledge Panel URL instead of a Maps URL, of the form
    # google.com/search?...&q=Business+Name&...
    parsed = urlparse(url)
    if "google." in parsed.netloc and parsed.path in ("/search", "/"):
        qs = parse_qs(parsed.query)
        if "q" in qs and qs["q"]:
            return unquote(qs["q"][0].replace("+", " "))

    return None


def resolve_place_id(user_input: str, gmaps_client: googlemaps.Client) -> str:
    user_input = user_input.strip()

    if user_input.startswith("ChIJ") or user_input.startswith("GhIJ"):
        try:
            gmaps_client.place(place_id=user_input, fields=["place_id"])
            return user_input
        except Exception:
            pass

    if user_input.isdigit():
        return _cid_to_place_id(user_input, gmaps_client)

    if user_input.startswith("http"):
        url = user_input
        # Any link that isn't already a full google.com/maps URL is treated
        # as a short link and expanded via redirect-following. This covers
        # goo.gl, maps.app.goo.gl, share.google, and any future short
        # domains Google introduces, without needing a hardcoded list.
        if "google.com/maps" not in url:
            url = _expand_short_link(url)

        cid = _extract_cid(url)
        if cid:
            return _cid_to_place_id(cid, gmaps_client)

        name = _extract_name_and_area(url)
        if name:
            result = gmaps_client.find_place(
                input=name,
                input_type="textquery",
                fields=["place_id"],
            )
            candidates = result.get("candidates", [])
            if candidates:
                return candidates[0]["place_id"]

    raise PlaceResolutionError(
        "Could not resolve a Place ID from the input given. "
        "Paste the full Google Business Profile / Maps share link, "
        "or paste the Place ID directly."
    )


def _cid_to_place_id(cid: str, gmaps_client: googlemaps.Client) -> str:
    probe_url = f"https://www.google.com/maps?cid={cid}"
    final_url = _expand_short_link(probe_url)
    name = _extract_name_and_area(final_url)
    if not name:
        raise PlaceResolutionError(f"Could not resolve CID {cid} to a business.")
    result = gmaps_client.find_place(
        input=name, input_type="textquery", fields=["place_id"]
    )
    candidates = result.get("candidates", [])
    if not candidates:
        raise PlaceResolutionError(f"Could not resolve CID {cid} to a Place ID.")
    return candidates[0]["place_id"]
