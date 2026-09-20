"""
Australian suburb / postcode / state lookup, backing the "search-bar"
autocomplete in the intake form's suburb and postcode fields.

Data: a bundled, trimmed snapshot of the community-maintained
australianpostcodes dataset (matthewproctor/australianpostcodes, MIT
licensed, official Australia Post "Delivery Area" localities only --
LVRs and PO-box-only entries excluded), stored at
components/data/au_localities.json as [[suburb, postcode, state], ...].

Bundled locally (not fetched live) so the autocomplete is instant and
works even if every external API this app talks to is down -- confirming
a suburb name shouldn't depend on network access.
"""

import json
import os

_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "au_localities.json")
_LOCALITIES = None


def _load():
    global _LOCALITIES
    if _LOCALITIES is None:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            rows = json.load(f)
        _LOCALITIES = [{"suburb": s, "postcode": p, "state": st} for s, p, st in rows]
    return _LOCALITIES


def search_by_suburb(query, limit=8):
    """
    Suburbs whose name starts with `query` (case-insensitive), then
    suburbs that merely contain it, each group alphabetical. A suburb
    with more than one postcode appears once per postcode -- each is a
    genuinely different, real combination.
    """
    query = (query or "").strip().lower()
    if not query:
        return []
    starts, contains = [], []
    for row in _load():
        name = row["suburb"].lower()
        if name.startswith(query):
            starts.append(row)
        elif query in name:
            contains.append(row)
    return (starts + contains)[:limit]


def search_by_postcode(query, limit=8):
    """Suburbs whose postcode starts with the digits typed so far."""
    query = (query or "").strip()
    if not query:
        return []
    matches = [row for row in _load() if row["postcode"].startswith(query)]
    matches.sort(key=lambda r: (r["postcode"], r["suburb"]))
    return matches[:limit]
