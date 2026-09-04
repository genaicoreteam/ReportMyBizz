"""
core/map_renderer.py

Renders the grid-of-dots map for each keyword using the `staticmap`
library, which draws on free OpenStreetMap tiles -- no Google Static Maps
billing involved, keeping this on the free tier.

Images are returned as base64 data URIs rather than written to disk, so
report generation needs no writable filesystem -- it runs the same on a
laptop as it does in a read-only serverless function (e.g. Vercel).
"""

import base64
import io

from staticmap import StaticMap, CircleMarker

GREEN = "#2F6B4F"
AMBER = "#C79A3A"
RED = "#B5533C"
DARK = "#1F3D2B"


def _color_for_rank(rank):
    if rank is None:
        return RED
    if rank <= 5:
        return GREEN
    if rank <= 10:
        return AMBER
    return RED


def render_grid_map(points_with_rank: list, center_lat: float, center_lng: float,
                     width=520, height=420):
    """Returns a `data:image/png;base64,...` URI ready to drop straight into
    an <img src>, or None if the tile render failed."""
    m = StaticMap(width, height, url_template=(
        "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"
    ))

    for p in points_with_rank:
        color = _color_for_rank(p["rank"])
        m.add_marker(CircleMarker((p["lng"], p["lat"]), color, 16))

    m.add_marker(CircleMarker((center_lng, center_lat), DARK, 20))

    try:
        image = m.render()
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except Exception:
        return None
