"""
core/map_renderer.py

Renders the grid-of-dots map for each keyword using the `staticmap`
library, which draws on free OpenStreetMap tiles -- no Google Static Maps
billing involved, keeping this on the free tier.

Every marker is labeled directly on the image (rank number, or a
competitor's badge number) instead of being a bare colored dot -- the
map should be readable at a glance, not require a separate legend to
decode. Real competitor locations (see rank_tracker.py) are plotted too,
so you can see where they actually sit relative to the business instead
of only reading their name in a table. In a dense downtown grid a
competitor can be only meters from a search point, so competitor pins
are nudged apart from grid dots and the "you" marker they'd otherwise
sit exactly on top of.

A search grid is a plain mathematical NxN square around the business,
so some points can genuinely fall in a lake, a bay, or open sea -- the
Nearby Search from that coordinate is still real and its result still
counts, but a dot floating in the middle of a lake reads as broken.
Grid dots are nudged onto the nearest dry pixel (sampling the map
tile's own water color) purely for where they're *drawn*; the rank
number they carry is still the one Google returned from the true point.

Images are returned as base64 data URIs rather than written to disk, so
report generation needs no writable filesystem -- it runs the same on a
laptop as it does in a read-only serverless function (e.g. Vercel).
"""

import math

from staticmap import StaticMap, CircleMarker
from staticmap.staticmap import _lon_to_x, _lat_to_y

from core.chart_renderer import to_data_uri, draw_center_text
from PIL import Image, ImageDraw, ImageFont
import config

# Mirrors config.REPORT_BRAND so the map's dot colors always agree with
# the rest of the report (KPI cards, keyword table, badges).
GREEN = config.REPORT_BRAND["good"]
AMBER = config.REPORT_BRAND["warn"]
RED = config.REPORT_BRAND["danger"]
DARK = config.REPORT_BRAND["navy"]
COMPETITOR = config.REPORT_BRAND["grad_start"]

# Internal render scale: staticmap tiles are fixed-resolution, so we
# render at 2x and downsample at the end for crisp anti-aliased text
# and circles instead of blocky ones.
SCALE = 2

DOT_R = 30 * SCALE
COMPETITOR_R = 26 * SCALE
YOU_HALO_R = DOT_R + 8 * SCALE
MIN_GAP = 4 * SCALE
MAX_LAND_SEARCH = 90 * SCALE

# OpenStreetMap's standard "carto" style renders all water (ocean, bays,
# lakes) as this exact color -- confirmed by sampling real tiles.
WATER_RGB = (170, 211, 223)
WATER_TOLERANCE = 12


def _color_for_rank(rank):
    if rank is None:
        return RED
    if rank <= 5:
        return GREEN
    if rank <= 10:
        return AMBER
    return RED


def _is_water(rgb):
    r, g, b = rgb[:3]
    return (abs(r - WATER_RGB[0]) <= WATER_TOLERANCE
            and abs(g - WATER_RGB[1]) <= WATER_TOLERANCE
            and abs(b - WATER_RGB[2]) <= WATER_TOLERANCE)


def _nearest_land(image, x, y, max_radius):
    """Searches outward in expanding rings for the nearest non-water
    pixel, so a grid dot doesn't visually float in a lake or the sea.
    Gives up and returns the original spot if no dry pixel is found
    within range (a report covering a genuinely offshore point should
    still show something rather than silently drop it)."""
    w, h = image.size
    ix, iy = int(round(x)), int(round(y))
    if not (0 <= ix < w and 0 <= iy < h) or not _is_water(image.getpixel((ix, iy))):
        return x, y

    step = max(4, max_radius // 12)
    r = step
    while r <= max_radius:
        samples = max(8, int(r / 6))
        for i in range(samples):
            angle = 2 * math.pi * i / samples
            sx, sy = ix + r * math.cos(angle), iy + r * math.sin(angle)
            six, siy = int(round(sx)), int(round(sy))
            if 0 <= six < w and 0 <= siy < h and not _is_water(image.getpixel((six, siy))):
                return sx, sy
        r += step
    return x, y


def _push_clear(x, y, r, obstacles):
    """Nudges (x, y) radially away from any obstacle (ox, oy, o_radius)
    it currently overlaps. A couple of passes is plenty for the handful
    of markers on one map -- this isn't a general layout solver, just
    enough so a competitor pin never lands exactly on top of a grid dot
    or the "you" halo, which real-world density otherwise causes often."""
    for _ in range(2):
        for ox, oy, o_r in obstacles:
            min_dist = r + o_r + MIN_GAP
            dx, dy = x - ox, y - oy
            dist = math.hypot(dx, dy)
            if dist < min_dist:
                if dist < 1e-6:
                    dx, dy, dist = 1.0, 0.0, 1.0
                scale = min_dist / dist
                x, y = ox + dx * scale, oy + dy * scale
    return x, y


def render_grid_map(points_with_rank: list, center_lat: float, center_lng: float,
                     competitors: list = None, width=520, height=400):
    """Returns a `data:image/png;base64,...` URI ready to drop straight
    into an <img src>, or None if the tile render failed.

    `competitors` is an optional list of {name, lat, lng} dicts (already
    filtered to real, nearby businesses -- see rank_tracker.py) plotted
    as small numbered pins so their position relative to the business is
    visible, not just their name in a table.
    """
    competitors = [c for c in (competitors or [])
                   if c.get("lat") is not None and c.get("lng") is not None][:3]

    w, h = width * SCALE, height * SCALE
    m = StaticMap(w, h, url_template=(
        "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"
    ))

    # Tiny markers purely so staticmap's automatic zoom/extent framing
    # spans the whole grid -- the actual visible circles are drawn by
    # hand afterward (below) at each point's real or water-nudged
    # position, not by staticmap's own marker rendering.
    for p in points_with_rank:
        m.add_marker(CircleMarker((p["lng"], p["lat"]), _color_for_rank(p["rank"]), 2 * SCALE))

    try:
        image = m.render()
    except Exception:
        return None

    def to_px(lat, lng):
        return (m._x_to_px(_lon_to_x(lng, m.zoom)),
                m._y_to_px(_lat_to_y(lat, m.zoom)))

    # Nudged purely off water -- not also spaced apart from each other.
    # Pushing overlapping dots apart risked cascading a dot back into
    # the water on the far side of a narrow shoreline; a business right
    # on a lakefront can have most of its grid overlap a strip of dry
    # land, and dots overlapping there is a far smaller visual problem
    # than one sitting in the lake.
    grid_draw_px = [_nearest_land(image, *to_px(p["lat"], p["lng"]), MAX_LAND_SEARCH)
                    for p in points_with_rank]
    cx, cy = _nearest_land(image, *to_px(center_lat, center_lng), MAX_LAND_SEARCH)

    draw = ImageDraw.Draw(image)

    # The business's own location is one of the grid points (searches
    # are run from it too, like any other point) -- rather than paint
    # over its real rank dot, ring it with a halo so it reads as "you"
    # without hiding the number underneath. Drawn before the labels
    # below so the rings sit behind the text, not clipping through it.
    for r, color, sw in ((YOU_HALO_R, DARK, 3 * SCALE),
                         (DOT_R + 3 * SCALE, "white", 3 * SCALE)):
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=sw)

    rank_font = ImageFont.load_default(size=11 * SCALE)
    for (x, y), p in zip(grid_draw_px, points_with_rank):
        color = _color_for_rank(p["rank"])
        draw.ellipse([x - DOT_R, y - DOT_R, x + DOT_R, y + DOT_R], fill=color)
        label = "20+" if p["rank"] is None else str(p["rank"])
        draw_center_text(draw, label, rank_font, "white", (x, y))

    # Competitors are drawn (not added as staticmap markers) so their
    # on-image position can be nudged clear of anything they'd
    # otherwise overlap -- a real, nearby competitor is very often only
    # meters from a search point in a dense downtown grid.
    obstacles = [(cx, cy, YOU_HALO_R)] + [(x, y, DOT_R) for x, y in grid_draw_px]
    badge_font = ImageFont.load_default(size=12 * SCALE)
    for idx, c in enumerate(competitors, start=1):
        x, y = to_px(c["lat"], c["lng"])
        x, y = _push_clear(x, y, COMPETITOR_R, obstacles)
        draw.ellipse([x - COMPETITOR_R, y - COMPETITOR_R, x + COMPETITOR_R, y + COMPETITOR_R],
                     fill=COMPETITOR, outline="white", width=int(2.5 * SCALE))
        draw_center_text(draw, str(idx), badge_font, "white", (x, y))
        obstacles.append((x, y, COMPETITOR_R))

    image = image.resize((width, height), Image.LANCZOS)
    return to_data_uri(image)
