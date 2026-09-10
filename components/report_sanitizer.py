"""
Defensive post-processing for the AI-generated report JSON.

Gemini/Claude are asked (see report_generation.py's prompt) to return one big
JSON object matching the report schema, but an LLM response is never 100%
guaranteed to match it: a whole section key can be omitted, a list can come
back empty, a number can arrive as `null`, a string like "N/A", or be missing
entirely. TemplateService.render() (services.py) renders eagerly with a
lenient Jinja2 `Undefined` -- which means looping over a *missing* list
(`{% for x in section.items %}` when `items` was never returned) raises
immediately and crashes the WHOLE report, not just that one section. Doing
arithmetic on a missing/non-numeric value (e.g. the price-history chart's
min/max, or a progress-ring's `score / 100`) crashes the same way.

`sanitize_report_data()` repairs the dict just before it reaches
TemplateService.render(): every field the template touches is guaranteed to
exist with the right type, every number that drives a chart/bar/ring is
guaranteed to be a real, safe number, and any section whose real content
ended up empty is flagged with `data_available=False` (+ a human-readable
`unavailable_reason`) so the template's existing `data_notice()` macro shows
an honest banner instead of a blank space or a broken-looking chart. This is
the "Report Generation's own validation pass" that TemplateService's
docstring already describes as the intended place to catch this -- it just
didn't exist yet.

This module never invents market data. Where a field can't be trusted, it is
replaced with an inert, clearly-labelled placeholder ("N/A" / "Data
unavailable") -- never a plausible-looking number -- and the enclosing
section is marked unavailable.
"""
from typing import Any, Dict, List, Optional

from components.variable_mapper import clean_number


# ------------------------------------------------------------------
# Generic coercion helpers
# ------------------------------------------------------------------

def _num(value: Any, default: float = 0) -> float:
    cleaned = clean_number(value)
    return cleaned if cleaned is not None else default


def _pct(value: Any, default: float = 0) -> float:
    """Coerce to a 0-100 number safe for use as a CSS width/percentage."""
    return max(0, min(100, _num(value, default)))


def _str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _bool(value: Any, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


def _list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_items(value: Any) -> List[Dict[str, Any]]:
    """Only the entries of a list that are actually objects -- junk entries
    (a stray string/number the model slipped into a list of objects) are
    dropped rather than crashing attribute access on them later."""
    return [item for item in _list(value) if isinstance(item, dict)]


def _mark_availability(section: Dict[str, Any], is_empty: bool, reason: str) -> None:
    """
    Sets data_available/unavailable_reason on a section dict so the
    template's data_notice() macro can render an honest banner.

    Respects an explicit `data_available: false` the AI may already have
    set (per the prompt's processing rules); otherwise falls back to
    flagging the section unavailable whenever its real content ended up
    empty after sanitization, even if the model stayed silent about it.
    """
    if section.get("data_available") is False:
        section["unavailable_reason"] = _str(section.get("unavailable_reason"), reason)
        return
    if is_empty:
        section["data_available"] = False
        section["unavailable_reason"] = _str(section.get("unavailable_reason"), reason)
    else:
        section["data_available"] = True


# ------------------------------------------------------------------
# Per-section sanitizers (one per top-level report_data key)
# ------------------------------------------------------------------

def _sanitize_snapshot(raw: Any) -> Dict[str, Any]:
    section = _dict(raw)
    stats_in = _dict_items(section.get("stats"))
    stats = [{
        "value": _str(s.get("value"), "N/A"),
        "label": _str(s.get("label"), "Metric"),
        "highlight": _bool(s.get("highlight"), False),
    } for s in stats_in]
    if not stats:
        stats = [{"value": "N/A", "label": "Data unavailable", "highlight": False}]

    section["match_score"] = int(_pct(section.get("match_score"), 0))
    section["stats"] = stats
    section["summary"] = _str(
        section.get("summary"),
        "Not enough verified data was available to summarize this suburb's overall match."
    )
    _mark_availability(
        section, not stats_in,
        "Suburb snapshot data isn't available for this area from our current data sources."
    )
    return section


def _sanitize_affordability(raw: Any) -> Dict[str, Any]:
    section = _dict(raw)
    stats_in = _dict_items(section.get("stats"))
    stats = [{"value": _str(s.get("value"), "N/A"), "label": _str(s.get("label"), "Metric")} for s in stats_in]
    if not stats:
        stats = [{"value": "N/A", "label": "Data unavailable"}]

    valid_directions = {"up", "down", "neutral"}
    trends = []
    for t in _dict_items(section.get("trends")):
        direction = _str(t.get("direction"), "neutral").lower()
        if direction not in valid_directions:
            direction = "neutral"
        trends.append({
            "label": _str(t.get("label"), "Trend"),
            "value": _str(t.get("value"), "N/A"),
            "direction": direction,
        })

    section["stats"] = stats
    section["trends"] = trends
    section["summary"] = _str(section.get("summary"), "Affordability data isn't available for this suburb yet.")
    _mark_availability(
        section, not stats_in,
        "Affordability data isn't available for this suburb from our current data sources."
    )
    return section


def _sanitize_rental(raw: Any) -> Dict[str, Any]:
    section = _dict(raw)
    metrics_in = _dict_items(section.get("metrics"))
    metrics = [{
        "label": _str(m.get("label"), "Metric"),
        "value": _str(m.get("value"), "N/A"),
        "bar_percent": _pct(m.get("bar_percent"), 0),
    } for m in metrics_in]
    if not metrics:
        metrics = [{"label": "Data unavailable", "value": "N/A", "bar_percent": 0}]

    section["metrics"] = metrics
    section["summary"] = _str(section.get("summary"), "Rental yield data isn't available for this suburb yet.")
    _mark_availability(
        section, not metrics_in,
        "Rental yield data isn't available for this suburb from our current data sources."
    )
    return section


def _sanitize_budget(raw: Any) -> Dict[str, Any]:
    section = _dict(raw)
    valid_styles = {"gold", "navy", "outline"}
    pills_in = _dict_items(section.get("pills"))
    pills = []
    for p in pills_in:
        style = _str(p.get("style"), "outline").lower()
        if style not in valid_styles:
            style = "outline"
        pills.append({
            "value": _str(p.get("value"), "N/A"),
            "label": _str(p.get("label"), "Metric"),
            "style": style,
        })
    if not pills:
        pills = [{"value": "N/A", "label": "Data unavailable", "style": "outline"}]

    section["units_percent"] = int(_pct(section.get("units_percent"), 0))
    section["pills"] = pills
    section["summary"] = _str(section.get("summary"), "Budget breakdown data isn't available for this suburb yet.")
    _mark_availability(
        section, not pills_in,
        "Budget breakdown data isn't available for this suburb from our current data sources."
    )
    return section


def _sanitize_growth(raw: Any) -> Dict[str, Any]:
    section = _dict(raw)
    metrics_in = _dict_items(section.get("metrics"))
    metrics = [{
        "value": _str(m.get("value"), "N/A"),
        "label": _str(m.get("label"), "Metric"),
        "bar_percent": _pct(m.get("bar_percent"), 0),
    } for m in metrics_in]
    if not metrics:
        metrics = [{"value": "N/A", "label": "Data unavailable", "bar_percent": 0}]

    section["category"] = _str(section.get("category"), "Unclassified")
    section["metrics"] = metrics
    section["summary"] = _str(section.get("summary"), "Growth outlook data isn't available for this suburb yet.")
    _mark_availability(
        section, not metrics_in,
        "Growth outlook data isn't available for this suburb from our current data sources."
    )
    return section


def _sanitize_infrastructure(raw: Any) -> Dict[str, Any]:
    section = _dict(raw)
    valid_tags = {"transport", "amenity", "community"}
    valid_status = {"active", "planned"}
    entries_in = _dict_items(section.get("entries"))
    entries = []
    for e in entries_in:
        tag_type = _str(e.get("tag_type"), "amenity").lower()
        if tag_type not in valid_tags:
            tag_type = "amenity"
        status_type = _str(e.get("status_type"), "planned").lower()
        if status_type not in valid_status:
            status_type = "planned"
        entries.append({
            "year": _str(e.get("year"), "TBC"),
            "title": _str(e.get("title"), "Infrastructure project"),
            "tag_type": tag_type,
            "tag_label": _str(e.get("tag_label"), tag_type.title()),
            "status_type": status_type,
            "status_label": _str(e.get("status_label"), status_type.title()),
            "value": _str(e.get("value"), ""),
        })
    if not entries:
        entries = [{
            "year": "N/A", "title": "Data unavailable", "tag_type": "amenity", "tag_label": "Unknown",
            "status_type": "planned", "status_label": "Unknown", "value": "",
        }]

    section["entries"] = entries
    section["summary"] = _str(section.get("summary"), "Infrastructure pipeline data isn't available for this suburb yet.")
    _mark_availability(
        section, not entries_in,
        "Infrastructure pipeline data isn't available for this suburb from our current data sources."
    )
    return section


def _sanitize_price_history(raw: Any) -> Dict[str, Any]:
    section = _dict(raw)

    points = []
    for p in _dict_items(section.get("points")):
        value = clean_number(p.get("value"))
        if value is None:
            # Never let an unparsable point corrupt the chart's min/max --
            # comparing a real number against None/a string is what crashes
            # the whole render, so entries that can't be trusted are dropped.
            continue
        color = p.get("highlight_color")
        points.append({
            "year": _str(p.get("year"), ""),
            "value": value,
            "highlight_color": color if isinstance(color, str) and color.strip() else "#162338",
        })

    has_real_points = bool(points)
    if not has_real_points:
        # Keep exactly one flat point so the template's min/max/division
        # logic always has something safe to run against; the notice banner
        # (set below) is what actually communicates the gap to the reader.
        points = [{"year": "N/A", "value": 0, "highlight_color": "#162338"}]

    labels = [_str(l) for l in _list(section.get("y_axis_labels")) if _str(l)]
    if len(labels) < 2:
        # The template divides by (len(y_axis_labels) - 1); fewer than 2
        # labels is both a division-by-zero risk and a broken-looking axis.
        labels = ["Low", "Mid-Low", "Mid-High", "High"]

    legend = [{
        "color": _str(l.get("color"), "#162338"),
        "label": _str(l.get("label"), ""),
    } for l in _dict_items(section.get("legend"))]

    section["points"] = points
    section["y_axis_labels"] = labels
    section["legend"] = legend
    _mark_availability(
        section, not has_real_points,
        "Historical price trend data isn't available for this suburb from our current data sources."
    )
    return section


def _sanitize_lifestyle(raw: Any) -> Dict[str, Any]:
    section = _dict(raw)
    scores_in = _dict_items(section.get("scores"))
    scores = [{
        "value": int(_pct(s.get("value"), 0)),
        "label": _str(s.get("label"), "Score"),
        "sublabel": _str(s.get("sublabel"), ""),
        "color": _str(s.get("color"), "#162338"),
    } for s in scores_in]
    if not scores:
        scores = [{"value": 0, "label": "Data unavailable", "sublabel": "", "color": "#162338"}]

    section["scores"] = scores
    section["summary"] = _str(section.get("summary"), "Lifestyle score data isn't available for this suburb yet.")
    _mark_availability(
        section, not scores_in,
        "Lifestyle score data isn't available for this suburb from our current data sources."
    )
    return section


def _sanitize_amenities(raw: Any) -> List[Dict[str, Any]]:
    return [{
        "icon": _str(a.get("icon"), "📍"),
        "count": _str(a.get("count"), "N/A"),
        "label": _str(a.get("label"), "Amenity"),
    } for a in _dict_items(raw)]


def _sanitize_day_in_life(raw: Any) -> List[Dict[str, Any]]:
    return [{
        "time": _str(d.get("time"), ""),
        "text": _str(d.get("text"), ""),
    } for d in _dict_items(raw)]


def _sanitize_community(raw: Any) -> Dict[str, Any]:
    section = _dict(raw)

    stats_in = _dict_items(section.get("stats"))
    stats = [{"value": _str(s.get("value"), "N/A"), "label": _str(s.get("label"), "Metric")} for s in stats_in]
    if not stats:
        stats = [{"value": "N/A", "label": "Data unavailable"}]

    def _hbar_list(key: str, default_label: str) -> List[Dict[str, Any]]:
        return [{
            "label": _str(b.get("label"), default_label),
            "value": _pct(b.get("value"), 0),
            "dark": _bool(b.get("dark"), False),
        } for b in _dict_items(section.get(key))]

    age_distribution = _hbar_list("age_distribution", "Age group")
    household_composition = _hbar_list("household_composition", "Household type")

    owner_vs_renter_in = _dict_items(section.get("owner_vs_renter"))
    fallback_labels = ["Owner Occupier", "Renter"]
    owner_vs_renter = []
    for i in range(2):
        if i < len(owner_vs_renter_in):
            o = owner_vs_renter_in[i]
            owner_vs_renter.append({
                "value": _pct(o.get("value"), 50),
                "label": _str(o.get("label"), fallback_labels[i]),
                "color": _str(o.get("color"), "#162338"),
            })
        else:
            # The template's owner-vs-renter row is laid out as a fixed
            # 2-column grid, so always hand it exactly two entries.
            owner_vs_renter.append({"value": 0, "label": fallback_labels[i], "color": "#162338"})

    section["stats"] = stats
    section["age_distribution"] = age_distribution
    section["household_composition"] = household_composition
    section["owner_vs_renter"] = owner_vs_renter
    section["type_summary"] = _str(section.get("type_summary"), "Not available")
    section["summary"] = _str(section.get("summary"), "Community demographic data isn't available for this area yet.")

    is_empty = not stats_in and not age_distribution and not household_composition and not owner_vs_renter_in
    _mark_availability(
        section, is_empty,
        "Community demographic data isn't available for this suburb from our current data sources."
    )
    return section


def _sanitize_schools(raw: Any) -> Dict[str, Any]:
    section = _dict(raw)
    list_in = _dict_items(section.get("list"))
    school_list = [{
        "type": _str(s.get("type"), "School"),
        "name": _str(s.get("name"), "Not specified"),
        "distance": _str(s.get("distance"), "N/A"),
        "score": int(_pct(s.get("score"), 0)),
    } for s in list_in]
    if not school_list:
        school_list = [{"type": "N/A", "name": "Data unavailable", "distance": "N/A", "score": 0}]

    family_fit = [{
        "label": _str(f.get("label"), "Family fit metric"),
        "value": _pct(f.get("value"), 0),
        "dark": _bool(f.get("dark"), False),
    } for f in _dict_items(section.get("family_fit"))]

    section["list"] = school_list
    section["family_fit"] = family_fit
    section["pending_notice"] = _str(section.get("pending_notice"), "")
    section["summary"] = _str(section.get("summary"), "School catchment data isn't available for this suburb yet.")
    section["verdict"] = _str(
        section.get("verdict"), "Not enough data to give a family-fit verdict for this suburb."
    )
    _mark_availability(
        section, not list_in,
        "School catchment and family-fit data isn't available for this suburb from our current data sources."
    )
    return section


def _sanitize_risk(raw: Any) -> Dict[str, Any]:
    section = _dict(raw)
    valid_levels = {"low", "medium", "high"}
    entries_in = _dict_items(section.get("entries"))
    entries = []
    for e in entries_in:
        level = _str(e.get("level"), "medium").lower()
        if level not in valid_levels:
            level = "medium"
        entries.append({
            "level": level,
            "title": _str(e.get("title"), "Risk factor"),
            "detail": _str(e.get("detail"), "No further detail available."),
            "badge": _str(e.get("badge"), level.upper()),
        })
    if not entries:
        entries = [{
            "level": "medium",
            "title": "Data unavailable",
            "detail": "No verified flood, bushfire, or planning risk data was available for this suburb.",
            "badge": "UNKNOWN",
        }]

    section["entries"] = entries
    section["summary"] = _str(section.get("summary"), "Risk data isn't available for this suburb yet.")
    section["disclaimer"] = _str(
        section.get("disclaimer"),
        "This report is general in nature and does not replace formal due diligence, a building/pest "
        "inspection, or professional planning advice."
    )
    _mark_availability(
        section, not entries_in,
        "Risk assessment data isn't available for this suburb from our current data sources."
    )
    return section


def _sanitize_verdict(raw: Any) -> Dict[str, Any]:
    section = _dict(raw)
    subs_in = _dict_items(section.get("subscores"))
    subscores = [{
        "label": _str(s.get("label"), "Sub-score"),
        "value": int(_pct(s.get("value"), 0)),
        "good": _bool(s.get("good"), False),
    } for s in subs_in]
    if not subscores:
        subscores = [{"label": "Data unavailable", "value": 0, "good": False}]

    strengths = [_str(x) for x in _list(section.get("strengths")) if _str(x)]
    considerations = [_str(x) for x in _list(section.get("considerations")) if _str(x)]
    comparables = [{
        "name": _str(c.get("name"), "Nearby suburb"),
        "postcode": _str(c.get("postcode"), ""),
        "price": _str(c.get("price"), "N/A"),
    } for c in _dict_items(section.get("comparable_suburbs"))]

    section["match_score"] = int(_pct(section.get("match_score"), 0))
    section["subscores"] = subscores
    section["strengths"] = strengths or ["Not enough verified data to list specific strengths for this suburb."]
    section["considerations"] = considerations or [
        "Not enough verified data to list specific considerations for this suburb."
    ]
    section["next_step"] = _str(
        section.get("next_step"), "Speak with your SmartPropGuide advisor for a tailored recommendation."
    )
    section["comparable_suburbs"] = comparables

    is_empty = not subs_in and not strengths and not considerations and not _num(section.get("match_score"), 0)
    _mark_availability(
        section, is_empty,
        "An overall verdict couldn't be confidently generated from the data available for this suburb."
    )
    return section


# ------------------------------------------------------------------
# Orchestrator
# ------------------------------------------------------------------

def sanitize_report_data(report_data: Any) -> Dict[str, Any]:
    """
    Repairs the AI-generated report dict just before it reaches
    TemplateService.render(), so a missing section, an empty list, or a
    `null`/non-numeric value the model returns can never crash the whole
    render or leave a chart doing arithmetic on `None`. See the module
    docstring above for the full rationale.
    """
    data = _dict(report_data)

    data["median_price"] = _str(data.get("median_price"), "N/A")
    data["clearance_rate"] = _str(data.get("clearance_rate"), "N/A")
    data["days_on_market"] = _str(data.get("days_on_market"), "N/A")

    data["snapshot"] = _sanitize_snapshot(data.get("snapshot"))
    data["affordability"] = _sanitize_affordability(data.get("affordability"))
    data["rental"] = _sanitize_rental(data.get("rental"))
    data["budget"] = _sanitize_budget(data.get("budget"))
    data["growth"] = _sanitize_growth(data.get("growth"))
    data["infrastructure"] = _sanitize_infrastructure(data.get("infrastructure"))
    data["price_history"] = _sanitize_price_history(data.get("price_history"))
    data["lifestyle"] = _sanitize_lifestyle(data.get("lifestyle"))
    data["amenities"] = _sanitize_amenities(data.get("amenities"))
    data["day_in_life"] = _sanitize_day_in_life(data.get("day_in_life"))
    data["community"] = _sanitize_community(data.get("community"))
    data["schools"] = _sanitize_schools(data.get("schools"))
    data["risk"] = _sanitize_risk(data.get("risk"))
    data["verdict"] = _sanitize_verdict(data.get("verdict"))

    return data
