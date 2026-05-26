"""Haversine distance and ward inference from coordinates."""

import math
from typing import Optional

# Earth's radius in metres
_EARTH_RADIUS_M = 6_371_000.0


def haversine_m(
    lat1: float, lon1: float, lat2: float, lon2: float,
) -> float:
    """Haversine distance between two points in metres."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Demo ward bounding boxes ─────────────────────────────────────────
# These are approximate centre points for the demo wards in seed.py.
# A real deployment would use a geocoding service (Nominatim, Google).
# Format: (lat, lon, radius_km) — points within radius_km of centre
# are inferred to belong to that ward.

_DEMO_WARD_CENTRES: dict[str, tuple[float, float, float]] = {
    "2": (19.0760, 72.8777, 2.0),   # Ward 2 — approximate Mumbai
    "4": (19.0800, 72.8900, 2.0),   # Ward 4
    "8": (19.0700, 72.8800, 2.0),   # Ward 8
    "11": (19.0900, 72.8950, 2.0),  # Ward 11
}


def infer_ward(lat: float, lon: float) -> Optional[str]:
    """Infer which demo ward a coordinate belongs to.

    Returns the ward number string if within radius of a known ward centre,
    or None if no match.
    """
    best_ward: Optional[str] = None
    best_dist = float("inf")

    for ward, (wlat, wlon, radius_km) in _DEMO_WARD_CENTRES.items():
        dist_m = haversine_m(lat, lon, wlat, wlon)
        if dist_m <= radius_km * 1000 and dist_m < best_dist:
            best_ward = ward
            best_dist = dist_m

    return best_ward


def ward_disagrees(
    text_ward: str, lat: float, lon: float, threshold_km: float = 5.0,
) -> bool:
    """Check whether the text-provided ward disagrees with coordinates.

    Returns True if the coordinates are > threshold_km from the ward
    centre, suggesting the user typed the wrong ward.
    """
    if text_ward not in _DEMO_WARD_CENTRES:
        return False
    wlat, wlon, _ = _DEMO_WARD_CENTRES[text_ward]
    dist_km = haversine_m(lat, lon, wlat, wlon) / 1000
    return dist_km > threshold_km
