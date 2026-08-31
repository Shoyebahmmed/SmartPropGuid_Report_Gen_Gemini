import json
import re
from typing import Any, Dict, Optional, Tuple

MATCHED_VARIABLES_TEMPLATE: Dict[str, Any] = {
    "suburb_name": None,
    "state": None,
    "postcode": None,
    "median_house_price": None,
    "median_unit_price": None,
    "price_growth_12m": None,
    "liveability_score": None,
    "match_score": None,
    "population": None,
    "entry_level_house_price": None,
    "entry_level_unit_price": None,
    "house_25th_percentile": None,
    "house_75th_percentile": None,
    "unit_25th_percentile": None,
    "unit_75th_percentile": None,
    "clearance_rate": None,
    "median_house_rent": None,
    "median_unit_rent": None,
    "gross_yield": None,
    "vacancy_rate": None,
    "days_on_market": None,
    "demand_supply_ratio": None,
    "units_percentage": None,
    "houses_percentage": None,
    "owner_occupier_percentage": None,
    "renter_percentage": None,
    "median_age": None,
    "median_household_income": None,
    "unemployment_rate": None,
    "top_household_type": None,
    "walk_score": None,
    "transit_score": None,
    "bike_score": None,
    "cafe_count": None,
    "supermarket_count": None,
    "green_space_count": None,
    "gym_count": None,
    "school_catchment_list": None,
    "school_ranking_scores": None,
    "flood_risk_level": None,
    "crime_index_score": None,
}


def _clean_number(val: Any) -> Optional[float]:
    """Helper to convert string/int/float numbers (e.g. '$1,200,000', '4.5%', '0.042', '35 days') to float/int."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        num = float(val)
        if num.is_integer():
            return int(num)
        return round(num, 4) if abs(num) < 1.0 else round(num, 2)
    val_str = str(val).strip()
    if not val_str or val_str.upper() in ["N/A", "NONE", "NULL", "-", "UNKNOWN"]:
        return None
    cleaned = re.sub(r"[^\d.-]", "", val_str)
    try:
        num = float(cleaned)
        if num.is_integer():
            return int(num)
        return round(num, 4) if abs(num) < 1.0 else round(num, 2)
    except (ValueError, TypeError):
        return None


def build_standardized_property_payload(
    suburb: str = "",
    state: str = "",
    postcode: str = "",
    property_type: str = "house",
    raw_api_data: Optional[Dict[str, Any]] = None,
    extra_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Transforms incoming suburb/HTAG data into the standard 41-variable payload
    along with an extra_variables bucket, and prints the formatted JSON to terminal.
    """
    matched = dict(MATCHED_VARIABLES_TEMPLATE)
    extra: Dict[str, Any] = {}

    # Basic location variables
    matched["suburb_name"] = suburb.strip() if suburb else None
    matched["state"] = state.strip().upper() if state else None
    matched["postcode"] = str(postcode).strip() if postcode else None

    is_unit = "unit" in property_type.lower() or "apartment" in property_type.lower() or "flat" in property_type.lower()

    if raw_api_data and isinstance(raw_api_data, dict):
        metrics = raw_api_data.get("metrics") or {}
        rcs = raw_api_data.get("rcs") or {}
        growth = raw_api_data.get("growth_rates") or {}
        demographics = raw_api_data.get("demographics") or {}
        supply_demand = raw_api_data.get("supply_demand") or {}

        # 1. Price metrics
        med_price = _clean_number(metrics.get("median_price") or raw_api_data.get("median_price"))
        if med_price is not None:
            if is_unit:
                matched["median_unit_price"] = med_price
            else:
                matched["median_house_price"] = med_price

        # Explicit house vs unit prices if available
        if "median_house_price" in raw_api_data:
            matched["median_house_price"] = _clean_number(raw_api_data.get("median_house_price"))
        if "median_unit_price" in raw_api_data:
            matched["median_unit_price"] = _clean_number(raw_api_data.get("median_unit_price"))

        # Price growth (12m / 1y)
        growth_1y = _clean_number(growth.get("1y") or raw_api_data.get("price_growth_12m") or raw_api_data.get("growth_12m"))
        matched["price_growth_12m"] = growth_1y

        # Yield, Vacancy, Days on Market
        matched["gross_yield"] = _clean_number(metrics.get("gross_yield") or raw_api_data.get("gross_yield"))
        matched["vacancy_rate"] = _clean_number(
            metrics.get("vacancy_rate") or supply_demand.get("vacancy_rate") or raw_api_data.get("vacancy_rate")
        )
        matched["days_on_market"] = _clean_number(metrics.get("days_on_market") or raw_api_data.get("days_on_market"))
        matched["clearance_rate"] = _clean_number(metrics.get("clearance_rate") or raw_api_data.get("clearance_rate"))

        # Demand Supply Ratio (DSR / Score)
        matched["demand_supply_ratio"] = _clean_number(
            raw_api_data.get("demand_supply_ratio") or raw_api_data.get("dsr") or supply_demand.get("dsr")
        )

        # RCS Score / Liveability / Match score
        rcs_overall = _clean_number(rcs.get("overall") or raw_api_data.get("rcs_score"))
        if rcs_overall is not None:
            matched["liveability_score"] = rcs_overall
            matched["match_score"] = rcs_overall

        # Demographics
        matched["population"] = _clean_number(demographics.get("population") or raw_api_data.get("population"))
        matched["median_age"] = _clean_number(demographics.get("median_age") or raw_api_data.get("median_age"))
        matched["median_household_income"] = _clean_number(
            demographics.get("median_household_income") or demographics.get("income") or raw_api_data.get("median_household_income")
        )
        matched["unemployment_rate"] = _clean_number(
            demographics.get("unemployment_rate") or raw_api_data.get("unemployment_rate")
        )
        matched["top_household_type"] = demographics.get("top_household_type") or raw_api_data.get("top_household_type")

        # Dwelling types & tenures
        matched["units_percentage"] = _clean_number(
            demographics.get("units_percentage") or demographics.get("unit_pct") or raw_api_data.get("units_percentage")
        )
        matched["houses_percentage"] = _clean_number(
            demographics.get("houses_percentage") or demographics.get("house_pct") or raw_api_data.get("houses_percentage")
        )
        matched["owner_occupier_percentage"] = _clean_number(
            demographics.get("owner_occupier_percentage") or demographics.get("owner_pct") or raw_api_data.get("owner_occupier_percentage")
        )
        matched["renter_percentage"] = _clean_number(
            demographics.get("renter_percentage") or demographics.get("renter_pct") or raw_api_data.get("renter_percentage")
        )

        # Walk, Transit, Bike scores
        matched["walk_score"] = _clean_number(raw_api_data.get("walk_score"))
        matched["transit_score"] = _clean_number(raw_api_data.get("transit_score"))
        matched["bike_score"] = _clean_number(raw_api_data.get("bike_score"))

        # Amenities
        matched["cafe_count"] = _clean_number(raw_api_data.get("cafe_count"))
        matched["supermarket_count"] = _clean_number(raw_api_data.get("supermarket_count"))
        matched["green_space_count"] = _clean_number(raw_api_data.get("green_space_count"))
        matched["gym_count"] = _clean_number(raw_api_data.get("gym_count"))

        # Schools & Risks
        matched["school_catchment_list"] = raw_api_data.get("school_catchment_list")
        matched["school_ranking_scores"] = raw_api_data.get("school_ranking_scores")
        matched["flood_risk_level"] = raw_api_data.get("flood_risk_level")
        matched["crime_index_score"] = _clean_number(raw_api_data.get("crime_index_score"))

        # Check for direct key matches if raw_api_data has any remaining matched variable keys
        for key in MATCHED_VARIABLES_TEMPLATE.keys():
            if matched[key] is None and key in raw_api_data and raw_api_data[key] is not None:
                val = raw_api_data[key]
                if isinstance(MATCHED_VARIABLES_TEMPLATE[key], (int, float)) or key.endswith(("_price", "_rate", "_score", "_percentage", "_count", "_income", "_age", "_yield", "_market", "_ratio", "_percentile", "population")):
                    matched[key] = _clean_number(val)
                else:
                    matched[key] = val

        # Populate extra_variables: everything else returned by the API outside the standard 41 schema
        mapped_keys = {
            "metrics", "rcs", "growth_rates", "demographics", "supply_demand"
        }
        for k, v in raw_api_data.items():
            if k not in MATCHED_VARIABLES_TEMPLATE and k not in mapped_keys:
                extra[k] = v

        # Also preserve nested API intelligence in extra_variables for narrative enrichment
        if rcs:
            extra["rcs_detailed"] = rcs
        if growth:
            extra["growth_rates_detailed"] = growth
        if demographics:
            extra["demographics_detailed"] = demographics
        if supply_demand:
            extra["supply_demand_detailed"] = supply_demand
        if "research_output" in raw_api_data:
            extra["htag_research_narrative"] = raw_api_data["research_output"]
        if "cycle_stage" in raw_api_data:
            extra["market_cycle_stage"] = raw_api_data["cycle_stage"]
        if "cycle_signal" in raw_api_data:
            extra["market_cycle_signal"] = raw_api_data["cycle_signal"]
        if "hapi_score" in raw_api_data:
            extra["hapi_score"] = raw_api_data["hapi_score"]

    if extra_context and isinstance(extra_context, dict):
        for k, v in extra_context.items():
            if k not in matched:
                extra[k] = v

    payload = {
        "matched_variables": matched,
        "extra_variables": extra
    }

    # Print pretty-printed JSON directly to the terminal
    print("\n" + "=" * 80)
    print("=== SMARTPROPGUIDE STANDARDIZED JSON PAYLOAD (41 MATCHED & EXTRA VARIABLES) ===")
    print("=" * 80)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("=" * 80 + "\n", flush=True)

    return payload
