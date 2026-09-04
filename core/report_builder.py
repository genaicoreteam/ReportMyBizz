"""
core/report_builder.py

The main pipeline. Every number that ends up in the final PDF traces back
to a live Google API response captured earlier in this file -- nothing is
templated-in as a guess. Where public data genuinely doesn't exist for a
field, the report says so explicitly instead of showing a fabricated value.
"""

import base64
import io
import os
import uuid
import googlemaps
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa

import config
from core.place_resolver import resolve_place_id
from core.place_details import get_place_details, summarize_header
from core.grid_utils import generate_grid
from core.rank_tracker import derive_keywords, run_geogrid
from core.review_analyzer import analyze_reviews
from core.profile_auditor import audit_profile
from core.scoring import compute_score
from core.map_renderer import render_grid_map
from core.report_visuals import build_visuals

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


class ReportGenerationError(Exception):
    pass


def build_report(user_link: str) -> dict:
    if not config.GOOGLE_MAPS_API_KEY:
        raise ReportGenerationError(
            "No Google Maps API key configured. Copy .env.example to .env "
            "and add your free key (see README.md)."
        )

    gmaps_client = googlemaps.Client(key=config.GOOGLE_MAPS_API_KEY)

    place_id = resolve_place_id(user_link, gmaps_client)

    details = get_place_details(place_id, gmaps_client)
    header = summarize_header(details)

    if header["lat"] is None or header["lng"] is None:
        raise ReportGenerationError("Google did not return coordinates for this business.")

    grid_points = generate_grid(
        header["lat"], header["lng"], config.GRID_SIZE, config.GRID_RADIUS_KM
    )
    keywords = derive_keywords(header["categories"], config.MAX_KEYWORDS)
    geogrid = run_geogrid(gmaps_client, place_id, grid_points, keywords)

    review_data = analyze_reviews(details)

    profile_audit = audit_profile(details, header)

    score = compute_score(
        geogrid["overall_average_rank"],
        header["rating"],
        header["review_count"],
        profile_audit["completion_pct"],
    )

    run_id = uuid.uuid4().hex[:10]

    # The same top few nearby competitors are plotted on every keyword's
    # map (rank_tracker.py already filtered these to real businesses
    # within the search radius -- no more out-of-town results mixed in).
    map_competitors = [
        c for c in geogrid["competitors"]
        if c.get("lat") is not None and c.get("lng") is not None
    ][:3]

    map_images = {}
    for kw, kw_data in geogrid["by_keyword"].items():
        map_images[kw] = render_grid_map(
            kw_data["points"], header["lat"], header["lng"],
            competitors=map_competitors,
        )

    visuals = build_visuals(geogrid, score, profile_audit, header, config.BRAND)

    context = {
        "header": header,
        "geogrid": geogrid,
        "keywords": keywords,
        "reviews": review_data,
        "profile_audit": profile_audit,
        "score": score,
        "map_images": map_images,
        "map_competitors": map_competitors,
        "visuals": visuals,
        "brand": config.BRAND,
        "grid_size": config.GRID_SIZE,
        "grid_radius_km": config.GRID_RADIUS_KM,
        "nearby_radius_m": config.NEARBY_SEARCH_RADIUS_M,
    }

    pdf_bytes = _render_pdf(context)
    context["pdf_base64"] = base64.b64encode(pdf_bytes).decode("ascii")
    context["run_id"] = run_id

    return context


def _render_pdf(context: dict) -> bytes:
    """Renders the report entirely in memory -- no writable filesystem
    needed, so this runs the same locally as it does in a read-only
    serverless function (e.g. Vercel)."""
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("report.html")
    html = template.render(**context)

    buf = io.BytesIO()
    pisa_status = pisa.CreatePDF(src=html, dest=buf)
    if pisa_status.err:
        raise ReportGenerationError("PDF generation failed while rendering the report.")
    return buf.getvalue()
