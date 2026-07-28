"""
htag_client.py
==============
Live HtAG data fetcher. Same module we built for the Flask prototype,
adapted to plug into Shoeb's Streamlit app.

USAGE FROM app.py
-----------------
    from htag_client import fetch_suburb, fetch_address, AmbiguousSuburb

    # By suburb
    data = fetch_suburb("Cheltenham VIC", property_type="house")

    # By address
    data = fetch_address("1 Charman Rd, Cheltenham VIC 3192")

    # Then pass to Claude:
    from claude_client import generate_report
    html = generate_report(
        intake_data=intake_form_dict,
        extra_context=data,
        template_html=template_string,
    )

ENV VAR REQUIRED
----------------
    HTAG_API_KEY=sk-project--...    (from developer.htagai.com)
"""

import os
import requests
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "https://api.htagai.com/v1"
API_KEY = os.environ.get("HTAG_API_KEY", "").strip()
HEADERS = {"x-api-key": API_KEY, "Accept": "application/json"}

SUPPORTED_STATES = ("VIC", "NSW")


class AmbiguousSuburb(Exception):
    """Raised when a suburb name matches multiple locations in VIC or NSW."""
    def __init__(self, name, candidates):
        self.name = name
        self.candidates = candidates
        labels = [f"{c['locality']} {c['state_name']} {c['postcode']}" for c in candidates]
        super().__init__(f"'{name}' matches: " + ", ".join(labels))


# ---------------------------------------------------------------------------
# Low-level HTTP
# ---------------------------------------------------------------------------

def _get(path, params=None):
    if not API_KEY:
        return None
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=HEADERS,
                         params=params or {}, timeout=15)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


def _post(path, body):
    if not API_KEY:
        return None
    try:
        r = requests.post(f"{BASE_URL}{path}", headers=HEADERS,
                          json=body, timeout=15)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


def _first(response):
    if not response:
        return {}
    if isinstance(response, dict):
        results = response.get("results")
        if isinstance(results, list) and results:
            return results[0]
        if "results" not in response:
            return response
    if isinstance(response, list) and response:
        return response[0]
    return {}


# ---------------------------------------------------------------------------
# Suburb resolution
# ---------------------------------------------------------------------------

def resolve_suburb(query):
    """
    Resolve a suburb from postcode, name, or "Name STATE" format.

    Examples:
      resolve_suburb("3192")           -> Cheltenham VIC
      resolve_suburb("Cheltenham VIC") -> Cheltenham VIC
      resolve_suburb("Cheltenham")     -> raises AmbiguousSuburb if both
                                          VIC and NSW have one

    Returns the locality dict, or None if not found.
    """
    query = query.strip()

    if query.isdigit() and len(query) == 4:
        data = _get("/reference/locality", {"postcode": query})
        return _first(data) if data else None

    parts = query.replace(",", " ").split()
    name_parts, postcode, state = [], None, None
    for p in parts:
        if p.isdigit() and len(p) == 4:
            postcode = p
        elif p.upper() in ("VIC", "NSW", "QLD", "WA", "SA", "TAS", "ACT", "NT"):
            state = p.upper()
        else:
            name_parts.append(p)
    name = " ".join(name_parts).upper()

    if postcode and name:
        data = _get("/reference/locality", {"postcode": postcode})
        results = data.get("results", []) if data else []
        for r in results:
            if r.get("locality", "").upper() == name:
                return r
        return results[0] if results else None

    data = _get("/reference/locality", {"name": name})
    results = data.get("results", []) if data else []
    if not results:
        return None

    if state:
        filtered = [r for r in results if r.get("state_name", "").upper() == state]
        if filtered:
            return filtered[0]

    supported = [r for r in results if r.get("state_name", "").upper() in SUPPORTED_STATES]
    if not supported:
        return None
    if len(supported) == 1:
        return supported[0]

    raise AmbiguousSuburb(name, supported)


# ---------------------------------------------------------------------------
# Suburb-level data fetch
# ---------------------------------------------------------------------------

def fetch_suburb(query, property_type="house"):
    """
    Full suburb-level fetch. Returns merged dict ready for Claude.

    Parameters
    ----------
    query : str
        Suburb name, postcode, or "Name STATE" format.
    property_type : str
        "house" or "unit".

    Returns
    -------
    dict with keys: locality, summary, scores, risk, fundamentals,
                    supply, demand, cycle, census, cash_rate,
                    property_type, mode
    """
    locality = resolve_suburb(query)
    if not locality:
        return {"error": f"Suburb '{query}' not found in VIC or NSW"}

    loc_pid = locality.get("loc_pid")
    params = {"level": "suburb", "area_id": loc_pid, "property_type": property_type}

    calls = {
        "summary":      ("/markets/summary",      params),
        "scores":       ("/markets/scores",       params),
        "risk":         ("/markets/risk",         params),
        "fundamentals": ("/markets/fundamentals", params),
        "supply":       ("/markets/supply",       params),
        "demand":       ("/markets/demand",       params),
        "cycle":        ("/markets/cycle",        params),
        "census":       ("/demographics/census-medians",
                         {"loc_pid": loc_pid, "cpi_adjusted": "true"}),
        "cash_rate":    ("/economics/cash-rate",  None),
    }

    results = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {k: pool.submit(_get, path, p) for k, (path, p) in calls.items()}
        for k, fut in futures.items():
            raw = fut.result()
            if k in ("census", "cash_rate"):
                results[k] = raw or {}
            else:
                results[k] = _first(raw)

    return {
        "mode": "suburb",
        "property_type": property_type,
        "locality": locality,
        **results,
    }


# ---------------------------------------------------------------------------
# Address-level data fetch (bonus -- v2 stretch)
# ---------------------------------------------------------------------------

def resolve_address(address):
    data = _post("/address/standardise", {"addresses": [address]})
    result = _first(data)
    if not result or result.get("error"):
        return None
    std = result.get("standardised_address", {})
    return {
        "address_key": result.get("address_key"),
        "input": result.get("input_address"),
        "street_number": std.get("street_number"),
        "street_name": std.get("street_name"),
        "street_type": std.get("street_type"),
        "suburb": std.get("suburb_or_locality"),
        "state": std.get("state"),
        "postcode": std.get("postcode"),
    }


def fetch_address(address, property_type="house"):
    """
    Address-level fetch. Fires ~18 endpoints in parallel and merges.
    """
    resolved = resolve_address(address)
    if not resolved:
        return {"error": f"Address '{address}' could not be standardised"}

    ak = resolved["address_key"]
    postcode = resolved.get("postcode")

    single = {
        "property_summary":   ("/property/summary",    {"address_key": ak}),
        "property_estimates": ("/property/estimates",  {"address_key": ak}),
        "property_history":   ("/property/history",    {"address_key": ak}),
        "property_market":    ("/property/market",     {"address_key": ak}),
        "schools":            ("/address/schools",     {"address_key": ak}),
    }
    multi = {
        "demographics":   ("/address/demographics",   {"address_keys": [ak]}),
        "environment":    ("/address/environment",    {"address_keys": [ak]}),
        "hazards":        ("/address/hazards",        {"address_keys": [ak]}),
        "transport":      ("/address/transport",      {"address_keys": [ak]}),
        "cbd_proximity":  ("/address/cbd-proximity",  {"address_keys": [ak]}),
        "walkability":    ("/address/walkability",    {"address_keys": [ak]}),
        "green_space":    ("/address/green-space",    {"address_keys": [ak]}),
        "essentials":     ("/address/essentials",     {"address_keys": [ak]}),
        "amenities":      ("/address/amenities",      {"address_keys": [ak]}),
        "coastal":        ("/address/coastal",        {"address_keys": [ak]}),
        "safety":         ("/address/safety",         {"address_keys": [ak]}),
        "nuisance":       ("/address/nuisance",       {"address_keys": [ak]}),
        "aviation":       ("/address/aviation",       {"address_keys": [ak]}),
    }
    all_calls = {**single, **multi}

    results = {}
    with ThreadPoolExecutor(max_workers=15) as pool:
        futures = {k: pool.submit(_get, path, p) for k, (path, p) in all_calls.items()}
        for k, fut in futures.items():
            results[k] = _first(fut.result())

    # Suburb-level overlay for context
    suburb_ctx = fetch_suburb(postcode, property_type) if postcode else {}

    return {
        "mode": "address",
        "property_type": property_type,
        "address": resolved,
        "address_data": results,
        "suburb_context": suburb_ctx,
    }
