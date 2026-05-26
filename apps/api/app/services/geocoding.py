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
# Format: (lat, lon, radius_km, area_name) — points within radius_km of
# the nearest centre are assigned that ward and area name.

_DEMO_WARD_CENTRES: dict[str, tuple[float, float, float, str]] = {
    "2":  (19.028, 72.849, 7.0, "Bandra West"),
    "4":  (18.995, 72.835, 7.0, "Byculla"),
    "8":  (19.043, 72.857, 7.0, "Khar West"),
    "11": (19.107, 72.856, 7.0, "Andheri West"),
    "1":  (18.906, 72.823, 7.0, "Colaba"),
    "3":  (18.960, 72.810, 7.0, "Worli"),
    "5":  (19.017, 72.857, 7.0, "Dadar"),
    "6":  (19.060, 72.830, 7.0, "Mahim"),
    "7":  (19.130, 72.840, 7.0, "Juhu"),
    "9":  (19.075, 72.890, 7.0, "Kurla"),
    "10": (19.050, 72.930, 7.0, "Ghatkopar"),
    "12": (19.080, 72.910, 7.0, "Chembur"),
    "13": (19.120, 72.910, 7.0, "Powai"),
    "14": (19.050, 72.840, 7.0, "Santacruz"),
    "15": (19.100, 72.830, 7.0, "Vile Parle"),
    "16": (19.020, 72.860, 7.0, "Lower Parel"),
    "17": (19.230, 72.850, 7.0, "Borivali"),
    "18": (19.190, 72.850, 7.0, "Malad"),
    "19": (19.160, 72.850, 7.0, "Goregaon"),
    "20": (19.200, 72.970, 7.0, "Mulund"),
    "21": (19.150, 72.960, 7.0, "Bhandup"),
}


def infer_ward(lat: float, lon: float) -> Optional[str]:
    """Infer which demo ward a coordinate belongs to.

    Returns the ward number string if within radius of a known ward centre,
    or None if no match.
    """
    best_ward: Optional[str] = None
    best_dist = float("inf")

    for ward, (wlat, wlon, radius_km, _area) in _DEMO_WARD_CENTRES.items():
        dist_m = haversine_m(lat, lon, wlat, wlon)
        if dist_m <= radius_km * 1000 and dist_m < best_dist:
            best_ward = ward
            best_dist = dist_m

    return best_ward


def infer_area(lat: float, lon: float) -> str:
    """Return locality name for coordinates, or empty string."""
    best_area = ""
    best_dist = float("inf")
    for _ward, (wlat, wlon, radius_km, area) in _DEMO_WARD_CENTRES.items():
        dist_m = haversine_m(lat, lon, wlat, wlon)
        if dist_m <= radius_km * 1000 and dist_m < best_dist:
            best_area = area
            best_dist = dist_m
    return best_area

def ward_disagrees(
    text_ward: str, lat: float, lon: float, threshold_km: float = 5.0,
) -> bool:
    """Check whether the text-provided ward disagrees with coordinates.

    Returns True if the coordinates are > threshold_km from the ward
    centre, suggesting the user typed the wrong ward.
    """
    if text_ward not in _DEMO_WARD_CENTRES:
        return False
    wlat, wlon, _, _area = _DEMO_WARD_CENTRES[text_ward]
    dist_km = haversine_m(lat, lon, wlat, wlon) / 1000
    return dist_km > threshold_km

# ── Nominatim reverse geocoding ─────────────────────────────────────

import json
import urllib.request
import urllib.parse
from dataclasses import dataclass

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_NOMINATIM_UA = "Janavani/1.0 (demo; contact@example.com)"

# Simple in-memory cache: rounded (lat, lon) → result
_cache: dict = {}


@dataclass
class LocationResult:
    suburb: str = ""
    road: str = ""
    area: str = ""
    landmark: str = ""
    sector: str = ""
    city: str = ""
    display_name: str = ""
    source: str = ""
    raw_json: str = ""


def reverse_geocode(lat: float, lon: float) -> LocationResult:
    """Resolve coordinates to structured location via Nominatim with cache."""
    # Round to ~100m to reuse cached results
    key = (round(lat, 3), round(lon, 3))
    if key in _cache:
        cached = _cache[key]
        import copy
        result = copy.copy(cached)
        result.source = "nominatim_cache"
        return result

    try:
        params = urllib.parse.urlencode({
            "lat": lat, "lon": lon, "format": "json",
            "addressdetails": 1, "zoom": 18,
        })
        req = urllib.request.Request(
            f"{_NOMINATUM_URL}?{params}",
            headers={"User-Agent": _NOMINATUM_UA},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return LocationResult(source="nominatim_error")

    addr = data.get("address", {})
    result = LocationResult(
        suburb=addr.get("suburb") or addr.get("neighbourhood") or addr.get("city_district") or "",
        road=addr.get("road") or addr.get("pedestrian") or "",
        area=addr.get("suburb") or addr.get("neighbourhood") or addr.get("city_district") or "",
        landmark=addr.get("amenity") or addr.get("tourism") or addr.get("historic") or "",
        sector=addr.get("county") or addr.get("state_district") or "",
        city=addr.get("city") or addr.get("town") or addr.get("municipality") or "",
        display_name=data.get("display_name", ""),
        source="nominatim",
        raw_json=json.dumps(data),
    )
    _cache[key] = result
    return result


def resolve_location(session, lat: float, lon: float) -> LocationResult:
    """Resolve location with fallback: cache → Nominatim → static → gps_only."""
    result = reverse_geocode(lat, lon)

    if not result.area:
        # Fall back to static centres
        area = infer_area(lat, lon)
        if area:
            result.area = area
            result.source = "static_centres"
        else:
            result.source = "gps_only"

    return result