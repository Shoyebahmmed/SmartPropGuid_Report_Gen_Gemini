"""
OSM Australia/Oceania ArcGIS Feature Service client.

Connects to the public "OpenStreetMap Layers" ArcGIS group
(https://www.arcgis.com/home/group.html?id=66d66956ab444ae89e8265f008704d4b)
filtered to Australia. These are public Esri Feature Services (no API key,
no login) maintained by OSM, licensed under ODbL. Geocoding (suburb name ->
lon/lat) uses OpenStreetMap's own free Nominatim service, the natural pairing
for this data -- also no API key, but rate-limited to ~1 request/second and
requires a real User-Agent (both respected below).

This module only fetches a bounded, pre-summarized set of the NEAREST named
features per layer (not a full area export) -- see summarize_nearby(), which
is what report_generation.py actually calls. query_layer()/geocode_suburb()
are the lower-level building blocks, kept general-purpose.

A restrictive network/proxy environment may block services-ap1.arcgis.com or
nominatim.openstreetmap.org; every public function here fails soft (returns
None/empty) rather than raising, so a report can still generate -- with the
AI's own estimate -- if this enrichment isn't reachable.
"""

import math
import time

import requests

LAYERS = {
    "landuse": "OSM_AU_Landuse",
    "shops": "OSM_AU_Shops",
    "waterways": "OSM_AU_Waterways",
    "buildings": "OSM_AU_Buildings",
    "medical": "OSM_AU_Medical",
    "highways": "OSM_AU_Highways",
    "pois": "OSM_AU_POIs",
}

# The layers actually useful for a "what's nearby" suburb report. waterways
# and buildings describe the area itself rather than named places a buyer
# would recognise, so they're left out of the report enrichment (still
# queryable directly via query_layer() for other uses). landuse is mostly
# unnamed zoning polygons (landuse=residential etc, name=null) but is where
# named parks/reserves/nature areas live -- the name-required filter in
# summarize_nearby() already excludes the unnamed zoning noise.
REPORT_LAYERS = ["shops", "medical", "highways", "pois", "landuse"]

ARCGIS_BASE = "https://services-ap1.arcgis.com/iA7fZQOnjY9D67Zx/arcgis/rest/services/{svc}/FeatureServer/0/query"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "SmartPropGuide-ReportEngine/1.0 (contact: operator)"

# Bounded, not paginated: this module summarizes the nearest few features per
# layer for a report, not a full-area export, so one page comfortably covers
# a realistic "nearby" radius without the extra round-trips full pagination
# (see the standalone OSM_AU CLI script this was adapted from) would cost
# during a synchronous report-generation request.
QUERY_RESULT_CAP = 200

# Primary OSM tag keys, in priority order, used to describe what a feature
# actually is (a feature typically has exactly one of these set).
KIND_FIELDS = ["amenity", "shop", "healthcare", "railway", "highway", "leisure", "tourism", "office", "landuse", "natural"]


def geocode_suburb(suburb: str, state: str = "", postcode: str = "", timeout: int = 15):
    """
    Resolves a suburb (+ optional state/postcode) to (lon, lat) via
    Nominatim's structured search. Returns None on any failure (no network,
    no match, malformed response) rather than raising -- callers should
    treat this as "OSM enrichment unavailable" and continue without it.
    """
    if not suburb or not suburb.strip():
        return None

    params = {
        "format": "json",
        "limit": 1,
        "countrycodes": "au",
        "city": suburb.strip(),
    }
    if state:
        params["state"] = state.strip()
    if postcode:
        params["postalcode"] = postcode.strip()

    try:
        resp = requests.get(
            NOMINATIM_URL, params=params, timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            return None
        return float(results[0]["lon"]), float(results[0]["lat"])
    except Exception:
        return None


def point_to_bbox(lon: float, lat: float, radius_m: float):
    """Rough equirectangular bbox around a point, radius in metres."""
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * math.cos(math.radians(lat)))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def _haversine_m(lon1, lat1, lon2, lat2):
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def query_layer(layer_key: str, bbox, where: str = "1=1", timeout: int = 20):
    """
    Queries one layer within a bbox (minx, miny, maxx, maxy in WGS84
    lon/lat). Returns a raw GeoJSON FeatureCollection, capped at
    QUERY_RESULT_CAP features (see module docstring). Returns an empty
    FeatureCollection on any failure.
    """
    svc = LAYERS.get(layer_key)
    if not svc:
        raise ValueError(f"Unknown OSM layer '{layer_key}'. Choose from: {', '.join(LAYERS)}")

    minx, miny, maxx, maxy = bbox
    params = {
        "where": where,
        "outFields": "*",
        "geometry": f"{minx},{miny},{maxx},{maxy}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outSR": 4326,
        "resultRecordCount": QUERY_RESULT_CAP,
        "f": "geojson",
    }

    try:
        resp = requests.get(
            ARCGIS_BASE.format(svc=svc), params=params, timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        data = resp.json()
        return {"type": "FeatureCollection", "features": data.get("features", [])}
    except Exception:
        return {"type": "FeatureCollection", "features": []}


def _geometry_point(geom: dict):
    """
    Returns a representative (lon, lat) for a feature's geometry, or None
    for a type with no single meaningful "distance from here" (a
    LineString -- a road, a waterway). Point geometries use their own
    coordinate; Polygon/MultiPolygon use a simple average-of-vertices
    centroid of the outer ring -- an approximation, but a fine one for
    "how far is this park roughly from the suburb centre" framing.
    """
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return None
    if gtype == "Point" and len(coords) >= 2:
        return coords[0], coords[1]
    if gtype == "Polygon" and coords and coords[0]:
        ring = coords[0]
        return sum(c[0] for c in ring) / len(ring), sum(c[1] for c in ring) / len(ring)
    if gtype == "MultiPolygon" and coords and coords[0] and coords[0][0]:
        ring = coords[0][0]
        return sum(c[0] for c in ring) / len(ring), sum(c[1] for c in ring) / len(ring)
    return None


def _feature_kind(props: dict) -> str:
    for key in KIND_FIELDS:
        val = props.get(key)
        if val:
            return str(val).replace("_", " ")
    return ""


def summarize_nearby(lon: float, lat: float, radius_m: float = 1500, top_n: int = 6):
    """
    Queries the report-relevant OSM layers around (lon, lat) and returns a
    compact summary suitable for dropping into the AI prompt's
    extra_variables -- NOT the raw GeoJSON, which would be far larger than
    useful. For each layer: a total count of named features found within
    the radius, and the `top_n` nearest, each as {name, kind, distance_m}.

    Returns None if every layer comes back empty (e.g. the service is
    unreachable, or the point genuinely has no OSM POI coverage) so the
    caller can skip adding an empty/misleading block to the prompt.
    """
    bbox = point_to_bbox(lon, lat, radius_m)
    summary = {}

    for layer_key in REPORT_LAYERS:
        fc = query_layer(layer_key, bbox)
        named = []
        for feat in fc["features"]:
            props = feat.get("properties", {}) or {}
            name = props.get("name")
            kind = _feature_kind(props)
            if not name or not kind:
                # No name, or no amenity/shop/etc tag at all -- the latter
                # is usually just a suburb/locality label point rather than
                # an actual place a buyer would recognise as "nearby".
                continue
            point = _geometry_point(feat.get("geometry") or {})
            if point is None:
                # A LineString (a road, a waterway) has no single
                # meaningful "distance from here" -- skip it.
                continue
            dist = _haversine_m(lon, lat, point[0], point[1])
            if dist > radius_m:
                continue
            named.append({
                "name": name,
                "kind": kind,
                "distance_m": round(dist),
            })

        if not named:
            continue
        named.sort(key=lambda x: x["distance_m"])
        summary[layer_key] = {
            "count_within_radius": len(named),
            "nearest": named[:top_n],
        }
        # Nominatim/ArcGIS are free public services -- a short pause between
        # the 4 report-layer queries is a light courtesy, not a hard limit.
        time.sleep(0.1)

    if not summary:
        return None

    return {
        "radius_m": radius_m,
        "layers": summary,
    }
