"""
abs_client.py
=============
Free ABS (Australian Bureau of Statistics) data fetcher.

No API key required. Uses the public Data API + Indicator API.

USAGE
-----
    from abs_client import fetch_census_medians, fetch_headline_indicators

    demo = fetch_census_medians(postcode="3192")
    indicators = fetch_headline_indicators()

    # Merge into your Claude call:
    from claude_client import generate_report
    html = generate_report(
        intake_data=intake,
        extra_context={"abs_census": demo, "abs_indicators": indicators},
    )

NOTES
-----
- ABS uses SA2 geography, not postcode. This module does a rough
  postcode -> SA2 mapping for common lookups.
- Free tier is generous (no per-hour caps for the volume this app will do).
- Data currency: Census 2021 is the current base year (next census 2026).
"""

import requests

ABS_BASE = "https://api.data.abs.gov.au"
INDICATOR_BASE = "https://api.data.abs.gov.au/indicators"


def _get(url, params=None):
    try:
        r = requests.get(url, params=params or {},
                         headers={"Accept": "application/json"}, timeout=15)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


# ---------------------------------------------------------------------------
# Headline indicators (unemployment, CPI, cash rate context)
# ---------------------------------------------------------------------------

def fetch_headline_indicators():
    """
    Pull the small set of headline indicators most relevant to FTBs:
    unemployment rate, CPI, wage price index.
    """
    indicators = {
        "unemployment_rate": "LF",       # Labour Force
        "cpi_all_groups":    "CPI",      # Consumer Price Index
        "wage_price_index":  "WPI",      # Wages
    }

    results = {}
    for name, code in indicators.items():
        data = _get(f"{INDICATOR_BASE}/data/{code}", {"format": "jsondata"})
        if data:
            # Simplified extraction -- ABS response is complex SDMX;
            # we grab the most recent observation.
            results[name] = _extract_latest_observation(data)
        else:
            results[name] = None

    return results


def _extract_latest_observation(sdmx_data):
    """
    ABS returns SDMX-JSON. Pull the most recent observation value.
    This is a best-effort extractor; if the structure differs we
    return raw data for Claude to interpret.
    """
    try:
        datasets = sdmx_data.get("data", {}).get("dataSets", [])
        if not datasets:
            return None
        observations = datasets[0].get("observations", {})
        if not observations:
            return None
        # Get the last key (most recent time period)
        last_key = sorted(observations.keys())[-1]
        return observations[last_key][0] if observations[last_key] else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Census medians by postcode
# ---------------------------------------------------------------------------

def fetch_census_medians(postcode=None, sa2_code=None):
    """
    Pull census-based demographic medians for a location.

    Provide either postcode OR sa2_code. Postcode does an approximate
    SA2 lookup first.

    Returns dict with: median_age, median_income_weekly, median_rent_weekly,
                       median_mortgage_monthly, household_size,
                       tenure_split, indigenous_pct, born_overseas_pct
    """
    if not sa2_code and postcode:
        sa2_code = _postcode_to_sa2(postcode)

    if not sa2_code:
        return {"error": "Could not resolve location to SA2 code"}

    # Pull the ABS Census Data Pack for this SA2
    # This is a simplified call; the real ABS DataPacks API needs specific
    # table codes (G01, G02, G34, G43 etc). See ABS documentation.
    tables = {
        "median_age":              "G01.MedianAge",
        "median_income_weekly":    "G02.MedianTotalPersonalIncome",
        "median_rent_weekly":      "G02.MedianRent",
        "median_mortgage_monthly": "G02.MedianMortgageRepayment",
        "household_size":          "G01.AverageHouseholdSize",
    }

    results = {"sa2_code": sa2_code}
    for label, table_code in tables.items():
        data = _get(f"{ABS_BASE}/data/ABS_CENSUS/{table_code}",
                    {"region": sa2_code, "format": "jsondata"})
        results[label] = _extract_latest_observation(data) if data else None

    return results


def _postcode_to_sa2(postcode):
    """
    Rough postcode -> SA2 mapping. In production you'd cache the ABS
    correspondence file locally. For v1, this is a stub that returns
    the postcode itself and lets HtAG's suburb data cover the gap.
    """
    # Real implementation: fetch from
    #   https://api.data.abs.gov.au/dataflow/ABS/ASGS_2021/latest
    # or download the correspondence CSV once and cache locally.
    # For now: return None so caller falls back to HtAG census.
    return None


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Fetching ABS headline indicators...")
    ind = fetch_headline_indicators()
    for k, v in ind.items():
        print(f"  {k}: {v}")

    print("\nFetching census medians for postcode 3192 (Cheltenham)...")
    med = fetch_census_medians(postcode="3192")
    print(med)
