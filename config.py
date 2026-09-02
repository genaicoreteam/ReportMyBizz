"""
config.py
Central place for all tunable settings. Nothing in this file fabricates
data -- it only controls HOW real data is fetched (grid size, radius,
keyword count, etc).
"""

import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()

GRID_SIZE = int(os.getenv("GRID_SIZE", 5))
GRID_RADIUS_KM = float(os.getenv("GRID_RADIUS_KM", 3))
NEARBY_SEARCH_RADIUS_M = 3000
MAX_RANK_DEPTH = 20

MAX_KEYWORDS = 5

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

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
