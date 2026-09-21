"""
Australian suburb / postcode / state lookup, backing the searchable
suburb and postcode dropdowns in the intake form.

Data: a bundled, trimmed snapshot of the community-maintained
australianpostcodes dataset (matthewproctor/australianpostcodes, MIT
licensed, official Australia Post "Delivery Area" localities only --
LVRs and PO-box-only entries excluded), stored at
components/data/au_localities.json as [[suburb, postcode, state], ...].

Bundled locally (not fetched live) so every option is available to
Streamlit's selectbox immediately -- selectbox already does real,
client-side, type-to-filter search over its options with no server
round trip per keystroke, which is exactly the "live search bar" UX
this needs and needs no extra component.
"""

import json
import os

_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "au_localities.json")
_OPTIONS = None
_LOOKUP = None


def _label(suburb, state, postcode):
    return f"{suburb}, {state} {postcode}"


def _load():
    global _OPTIONS, _LOOKUP
    if _OPTIONS is None:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            rows = json.load(f)
        options = []
        lookup = {}
        for suburb, postcode, state in rows:
            label = _label(suburb, state, postcode)
            options.append(label)
            lookup[label] = {"suburb": suburb, "postcode": postcode, "state": state}
        _OPTIONS = options
        _LOOKUP = lookup
    return _OPTIONS, _LOOKUP


def all_options():
    """All ~18k 'Suburb, STATE postcode' labels, and a label -> record
    lookup. Same list backs both the Suburb and Postcode dropdowns --
    Streamlit's selectbox filters on the full label text client-side, so
    typing a suburb name or a postcode both narrow it down correctly."""
    return _load()


def label_for(suburb, postcode, state):
    """The confirmed label for a (suburb, postcode, state) triple already
    held in session state, so a dropdown can show it as pre-selected
    after a rerun -- or None if that exact combination isn't in the
    bundled dataset (e.g. it was set some other way)."""
    if not (suburb and postcode and state):
        return None
    label = _label(suburb, state, postcode)
    _, lookup = _load()
    return label if label in lookup else None


def nearby_candidates(suburb, postcode, state, count=2):
    """
    A free, offline proxy for "nearby suburbs": the `count` other real
    localities in the same state whose postcode is numerically closest to
    this one (Australian postcodes are allocated in regional blocks, so
    a small numeric gap usually means genuinely nearby), excluding the
    suburb itself. No geocoding/network round trip needed.

    Used to pick real comparison candidates for HTAG's suburb-comparison
    agent -- picking WHICH suburbs to compare is necessarily a judgment
    call, but every number that comes back for them is real HTAG data,
    not invented.
    """
    try:
        target_pc = int(postcode)
    except (TypeError, ValueError):
        return []
    state = (state or "").strip().upper()
    suburb_norm = (suburb or "").strip().lower()

    scored = []
    for row in _load()[1].values():
        if row["state"] != state or row["suburb"].strip().lower() == suburb_norm:
            continue
        try:
            pc = int(row["postcode"])
        except ValueError:
            continue
        if pc == target_pc:
            # Same postcode as the target usually means a delivery-centre/PO
            # alias sharing that postcode, not a genuinely distinct nearby
            # suburb -- skip it in favour of the closest DIFFERENT postcode.
            continue
        scored.append((abs(pc - target_pc), row))
    scored.sort(key=lambda x: x[0])

    picked, seen = [], set()
    for _, row in scored:
        name_key = row["suburb"].strip().lower()
        if name_key in seen:
            continue
        seen.add(name_key)
        picked.append(row)
        if len(picked) >= count:
            break
    return picked
