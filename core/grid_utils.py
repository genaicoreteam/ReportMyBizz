"""
core/grid_utils.py
Generates an NxN grid of lat/lng points around a business, used to
simulate "searches from nearby locations" the same way LocalFalcon /
Grexa-style geogrid tools do.
"""

import math


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in meters."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def generate_grid(center_lat: float, center_lng: float, grid_size: int,
                   radius_km: float):
    if grid_size < 1:
        raise ValueError("grid_size must be >= 1")

    points = []
    km_per_deg_lat = 110.574
    km_per_deg_lng = 111.320 * math.cos(math.radians(center_lat))

    if grid_size == 1:
        return [(center_lat, center_lng)]

    step_km = (2 * radius_km) / (grid_size - 1)
    half = (grid_size - 1) / 2
    for row in range(grid_size):
        for col in range(grid_size):
            d_lat_km = (row - half) * step_km
            d_lng_km = (col - half) * step_km
            lat = center_lat + (d_lat_km / km_per_deg_lat)
            lng = center_lng + (d_lng_km / km_per_deg_lng)
            points.append((round(lat, 6), round(lng, 6)))
    return points
