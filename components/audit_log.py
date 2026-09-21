"""
Per-report audit trail: one CSV row per report generated, recording the
exact real values pulled from HTAG, ABS and ArcGIS/OSM for that suburb,
next to what the AI actually put in the finished report.

Exists so a generated report's numbers can be traced back to a real
source query rather than taken on faith -- every HTAG/ABS/OSM column
below is copied verbatim from that service's response for this exact
report, not recomputed or touched by the AI in any way.

Sections in this run flagged data_available=false (report_sanitizer.py)
are recorded too: that flag means the AI declined to guess for a section
rather than inventing a number, which is itself part of the trail.
"""

import csv
import datetime
import os

from components.variable_mapper import MATCHED_VARIABLES_TEMPLATE

LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "report_audit_log.csv")

# Real HTAG fields only -- suburb_name/state/postcode are already in the
# meta columns, so they're dropped here to avoid duplicating them.
_HTAG_FIELDS = [k for k in MATCHED_VARIABLES_TEMPLATE.keys() if k not in ("suburb_name", "state", "postcode")]

_OSM_LAYERS = ["shops", "medical", "highways", "pois", "landuse"]

_SANITIZED_SECTIONS = [
    "snapshot", "affordability", "rental", "budget", "growth", "infrastructure",
    "price_history", "lifestyle", "community", "schools", "risk", "verdict",
]

_META_FIELDS = [
    "timestamp", "suburb", "postcode", "state", "property_type", "budget_range",
    "intention", "data_source_mode",
]

_ABS_FIELDS = [
    "abs_lga_name", "abs_lga_code", "abs_sa2_name", "abs_state_name",
    "abs_median_age_years", "abs_median_personal_income_weekly",
    "abs_median_family_income_weekly", "abs_median_household_income_weekly",
    "abs_median_mortgage_repayment_monthly", "abs_median_rent_weekly",
    "abs_avg_persons_per_bedroom", "abs_avg_household_size",
    "abs_population_latest_year", "abs_population_latest",
    "abs_population_growth_1yr_pct", "abs_population_growth_5yr_pct",
]

_OSM_FIELDS = ["osm_radius_m"]
for _layer in _OSM_LAYERS:
    _OSM_FIELDS += [f"osm_{_layer}_count", f"osm_{_layer}_nearest_name", f"osm_{_layer}_nearest_distance_m"]

_REPORT_FIELDS = [
    "report_median_price", "report_clearance_rate", "report_days_on_market",
    "report_match_score", "report_sections_flagged_unavailable",
]

FIELDNAMES = (
    _META_FIELDS
    + [f"htag_{k}" for k in _HTAG_FIELDS]
    + _ABS_FIELDS
    + _OSM_FIELDS
    + _REPORT_FIELDS
)


def _htag_row(matched_variables):
    matched_variables = matched_variables or {}
    return {f"htag_{k}": matched_variables.get(k) for k in _HTAG_FIELDS}


def _abs_row(abs_stats):
    if not abs_stats:
        return {k: None for k in _ABS_FIELDS}
    region = abs_stats.get("region") or {}
    medians = abs_stats.get("census_2021_medians") or {}
    population = abs_stats.get("population") or {}
    return {
        "abs_lga_name": region.get("lga_name"),
        "abs_lga_code": region.get("lga_code"),
        "abs_sa2_name": region.get("sa2_name"),
        "abs_state_name": region.get("state_name"),
        "abs_median_age_years": medians.get("median_age_years"),
        "abs_median_personal_income_weekly": medians.get("median_personal_income_weekly"),
        "abs_median_family_income_weekly": medians.get("median_family_income_weekly"),
        "abs_median_household_income_weekly": medians.get("median_household_income_weekly"),
        "abs_median_mortgage_repayment_monthly": medians.get("median_mortgage_repayment_monthly"),
        "abs_median_rent_weekly": medians.get("median_rent_weekly"),
        "abs_avg_persons_per_bedroom": medians.get("avg_persons_per_bedroom"),
        "abs_avg_household_size": medians.get("avg_household_size"),
        "abs_population_latest_year": population.get("latest_year"),
        "abs_population_latest": population.get("latest_population"),
        "abs_population_growth_1yr_pct": population.get("population_growth_1yr_pct"),
        "abs_population_growth_5yr_pct": population.get("population_growth_5yr_pct"),
    }


def _osm_row(osm_nearby):
    row = {k: None for k in _OSM_FIELDS}
    if not osm_nearby:
        return row
    row["osm_radius_m"] = osm_nearby.get("radius_m")
    layers = osm_nearby.get("layers") or {}
    for layer in _OSM_LAYERS:
        layer_data = layers.get(layer) or {}
        row[f"osm_{layer}_count"] = layer_data.get("count_within_radius")
        nearest_list = layer_data.get("nearest") or []
        if nearest_list:
            row[f"osm_{layer}_nearest_name"] = nearest_list[0].get("name")
            row[f"osm_{layer}_nearest_distance_m"] = nearest_list[0].get("distance_m")
    return row


def _report_row(report_data):
    report_data = report_data or {}
    flagged = [
        section for section in _SANITIZED_SECTIONS
        if isinstance(report_data.get(section), dict) and report_data[section].get("data_available") is False
    ]
    return {
        "report_median_price": report_data.get("median_price"),
        "report_clearance_rate": report_data.get("clearance_rate"),
        "report_days_on_market": report_data.get("days_on_market"),
        "report_match_score": (report_data.get("snapshot") or {}).get("match_score"),
        "report_sections_flagged_unavailable": "; ".join(flagged) if flagged else "",
    }


OVERFLOW_PATH = os.path.join(os.path.dirname(LOG_PATH), "report_audit_log.pending.csv")


def _write_row(path, row):
    file_exists = os.path.isfile(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def log_report(meta, matched_variables, abs_stats, osm_nearby, report_data, path=LOG_PATH):
    """
    Append one audit row for a just-generated report. Never raises -- a
    logging failure must not break report generation; the caller still
    wraps this in its own try/except as a last resort.

    If `path` is locked (e.g. open in Excel, which takes an exclusive
    lock on Windows), the row is written to report_audit_log.pending.csv
    next to it instead of being silently dropped -- merge that file's
    rows into the main log once it's closed. Returns the path actually
    written to, or None if both writes failed.
    """
    row = dict.fromkeys(FIELDNAMES)
    row.update(meta)
    row.update(_htag_row(matched_variables))
    row.update(_abs_row(abs_stats))
    row.update(_osm_row(osm_nearby))
    row.update(_report_row(report_data))

    try:
        _write_row(path, row)
        return path
    except OSError:
        pass

    try:
        _write_row(OVERFLOW_PATH, row)
        return OVERFLOW_PATH
    except OSError:
        return None
