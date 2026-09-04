"""
config.py
Central place for all tunable settings. Nothing in this file fabricates
data -- it only controls HOW real data is fetched (grid size, radius,
keyword count, etc).
"""

import os
import secrets
from dotenv import load_dotenv

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()

# Flask signs session/flash cookies with this. It must stay stable across
# requests -- on a serverless deployment each cold start is a fresh
# process, so a key generated at import time (os.urandom(...)) differs
# between invocations and silently breaks flash messages/sessions
# whenever a redirect happens to land on a different instance than the
# request that set it. Set FLASK_SECRET_KEY in the environment for any
# deployed instance; the random fallback is fine for a single local
# `python app.py` process.
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "").strip() or secrets.token_hex(24)

GRID_SIZE = int(os.getenv("GRID_SIZE", 5))
GRID_RADIUS_KM = float(os.getenv("GRID_RADIUS_KM", 3))
NEARBY_SEARCH_RADIUS_M = 3000
MAX_RANK_DEPTH = 20

MAX_KEYWORDS = 5

BRAND = {
    "green_dark": "#1F3D2B",
    "green": "#2F6B4F",
    "green_light": "#7FAE8C",
    "cream": "#FAF6EC",
    "cream_dark": "#F0E9D8",
    "text": "#243028",
    "danger": "#B5533C",
    "warn": "#C79A3A",
    "good": "#2F6B4F",
}

# Color theme for the generated PDF report specifically (the web page
# you're reading this on keeps its own green/cream identity -- this is
# just the color language used *inside* each report: the header
# gradient, score rings, and Good/Average/Poor badges).
REPORT_BRAND = {
    "grad_start": "#5A3FE0",   # header gradient, indigo -> blue
    "grad_end": "#3E8EF7",
    "navy": "#1E2233",         # map caption bars, "you" marker halo
    "text": "#1F2430",
    "muted": "#8B93A3",
    "page_bg": "#F0F1F5",
    "card_bg": "#FFFFFF",
    "border": "#E9EAF0",
    "good": "#3DA34D",
    "warn": "#EAA23A",
    "danger": "#EF4060",
    "good_bg": "#E6F6E9",
    "warn_bg": "#FDF1DE",
    "danger_bg": "#FCE3EA",
}
