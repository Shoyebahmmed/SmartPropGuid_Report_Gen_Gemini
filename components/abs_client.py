"""
ABS (Australian Bureau of Statistics) Data API client.

https://www.abs.gov.au/statistics/application-programming-interfaces-apis/data-api-user-guide

Pairs with osm_client.py, but answers a different question:

  OSM (osm_client.py): spatial query  -> bounding box -> buildings/shops/etc near a point
  ABS  (this file):     statistical query -> region code + time -> stats ABOUT an area
                         (median income, rent, mortgage repayments, household size,
                         population trend -- from the actual 2021 Census + annual ERP)

Region resolution (suburb -> the LGA the ABS stats are keyed by) uses ABS's own
official ASGS2021 boundary service at geo.abs.gov.au -- a point-in-polygon spatial
query against the real Census geography, not name-matching -- so "Bondi" correctly
resolves to Waverley council, "Mosman" to Mosman, etc. No API key / login needed for
either the boundary service or the data API (ABS removed the key requirement Nov 2024).

Every public function here fails soft (returns None/{}) rather than raising, so a
report can still generate -- with the AI's own estimate -- if ABS is unreachable.
"""

import csv
import io
import json
import urllib.parse
import urllib.request

DATA_BASE = "https://data.api.abs.gov.au/rest"
GEO_BASE = "https://geo.abs.gov.au/arcgis/rest/services/ASGS2021"
USER_AGENT = "SmartPropGuide-ReportEngine/1.0 (contact: operator)"

# Census 2021 "G02 Selected medians and averages" -- one row per LGA per code below.
MEDIANS_DATAFLOW = "C21_G02_LGA"
MEDAVG_LABELS = {
    "1": "median_age_years",
    "2": "median_personal_income_weekly",
    "3": "median_family_income_weekly",
    "4": "median_household_income_weekly",
    "5": "median_mortgage_repayment_monthly",
    "6": "median_rent_weekly",
    "7": "avg_persons_per_bedroom",
    "8": "avg_household_size",
}

# Estimated Resident Population by LGA, annually updated (not census-locked).
POPULATION_DATAFLOW = "ERP_LGA2025"


def _get_text(url, params, accept_csv=True, timeout=20):
    try:
        full = url + "?" + urllib.parse.urlencode(params)
        headers = {"User-Agent": USER_AGENT}
        if accept_csv:
            headers["Accept"] = "application/vnd.sdmx.data+csv"
        req = urllib.request.Request(full, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return None


def resolve_region(lon, lat, timeout=15):
    """
    Point-in-polygon lookup against ABS's own official ASGS2021 boundaries
    (the same geography the Census/ERP data below is keyed by) -- so this is
    exact, not a fuzzy name match.

    Returns {"lga_code","lga_name","sa2_code","sa2_name","state_name"}, or
    None if the point can't be resolved (e.g. offshore, or ABS unreachable).
    """
    geom = json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}})
    params = {
        "geometry": geom,
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "false",
        "f": "json",
    }
    field_map = {
        "SA2": {"sa2_code_2021": "sa2_code", "sa2_name_2021": "sa2_name", "state_name_2021": "state_name"},
        "LGA": {"lga_code_2021": "lga_code", "lga_name_2021": "lga_name"},
    }

    result = {}
    for layer, keys in field_map.items():
        text = _get_text(f"{GEO_BASE}/{layer}/FeatureServer/0/query", params, accept_csv=False, timeout=timeout)
        if not text:
            continue
        try:
            data = json.loads(text)
        except ValueError:
            continue
        features = data.get("features") or []
        if not features:
            continue
        attrs = features[0].get("attributes", {})
        for src, dst in keys.items():
            if attrs.get(src) not in (None, ""):
                result[dst] = attrs[src]

    return result or None


def _fetch_dataflow_rows(dataflow_id, timeout=30):
    """
    Full pull of one dataflow as CSV rows. Each ABS dataflow here is already
    scoped to one topic (a few thousand rows nationally, not millions like
    OSM buildings), so -- unlike osm_client's bounding-box queries -- pulling
    the whole thing and filtering client-side is simpler and reliable, rather
    than guessing SDMX's dot-separated dimension-key ordering per dataflow.
    """
    text = _get_text(f"{DATA_BASE}/data/ABS,{dataflow_id}/all", {"format": "csv"}, timeout=timeout)
    if not text:
        return []
    return list(csv.DictReader(io.StringIO(text)))


def fetch_selected_medians(lga_code, timeout=30):
    """
    Census 2021 "selected medians and averages" for one LGA: median age,
    personal/family/household income, mortgage repayment, rent, household
    size. Returns a flat dict keyed by MEDAVG_LABELS, or {} if unavailable.
    """
    lga_code = str(lga_code)
    out = {}
    for row in _fetch_dataflow_rows(MEDIANS_DATAFLOW, timeout=timeout):
        if row.get("REGION") != lga_code:
            continue
        label = MEDAVG_LABELS.get(row.get("MEDAVG"))
        if not label:
            continue
        try:
            out[label] = float(row["OBS_VALUE"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def fetch_population_trend(lga_code, timeout=30):
    """
    Estimated Resident Population, 2001-latest, for one LGA, plus 1yr/5yr
    growth percentages computed from the real series. Returns {} if
    unavailable.
    """
    lga_code = str(lga_code)
    series = {}
    for row in _fetch_dataflow_rows(POPULATION_DATAFLOW, timeout=timeout):
        if row.get("REGION") != lga_code:
            continue
        try:
            series[int(row["TIME_PERIOD"])] = float(row["OBS_VALUE"])
        except (KeyError, TypeError, ValueError):
            continue
    if not series:
        return {}

    latest_year = max(series)
    latest = series[latest_year]
    out = {"latest_year": latest_year, "latest_population": int(latest)}

    prev1 = series.get(latest_year - 1)
    if prev1:
        out["population_growth_1yr_pct"] = round((latest - prev1) / prev1 * 100, 2)
    prev5 = series.get(latest_year - 5)
    if prev5:
        out["population_growth_5yr_pct"] = round((latest - prev5) / prev5 * 100, 2)

    return out


def summarize_region_stats(lon, lat, timeout=30):
    """
    Main entry point -- mirrors osm_client.summarize_nearby()'s contract.
    Resolves (lon, lat) to its official LGA via ABS's own boundaries, then
    pulls real Census 2021 medians and the ERP population trend for that
    LGA. Fails soft: returns None if the region can't be resolved or ABS
    has no data for it, so report generation is never blocked by this.
    """
    region = resolve_region(lon, lat, timeout=timeout)
    if not region or not region.get("lga_code"):
        return None

    medians = fetch_selected_medians(region["lga_code"], timeout=timeout)
    population = fetch_population_trend(region["lga_code"], timeout=timeout)
    if not medians and not population:
        return None

    return {
        "region": region,
        "census_2021_medians": medians or None,
        "population": population or None,
    }
