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
