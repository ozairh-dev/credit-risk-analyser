"""Point-in-time filtering of a companyfacts payload.

**Why this exists, and why it is not optional.** The engine's selection layer
prefers the most recently *filed* value for a (concept, period type, period end)
— that is D14/D15 supersession, and it is correct for analysing a company today.
For a backtest it is hindsight: a FY2018 figure restated in a 2021 filing would
be used to "predict" a 2019 bankruptcy. The restatement is information that did
not exist at the decision date.

So a point-in-time run drops every fact **filed after the cutoff** before the
payload reaches the engine. Two properties matter:

1. **It is a payload transform, not an engine change.** `pipeline.analyse(raw)`
   takes a dict. Filtering the dict leaves every engine module byte-identical,
   which is what the Phase A freeze requires. The alternative — an `as_of`
   parameter threaded through `normalise/selection.py` — would be a change to
   the authoritative engine for the benefit of a test harness.
2. **It filters on `filed`, never on `end` or `fy`.** `fy` is the *filing's*
   fiscal-year stamp, not the fact's period (D19's fy-stamp trap, which this
   project has now hit four times). `end` is the period the fact describes,
   which says nothing about when it became public. Only `filed` answers "could
   an analyst have seen this".

A fact with no `filed` date is DROPPED, not kept: admitting a fact whose
publication date is unknown would silently reintroduce the leak this module
exists to close (CLAUDE.md rule 9 — fail safe).
"""

import copy


def filter_payload(raw: dict, as_of: str) -> dict:
    """A copy of `raw` holding only facts filed on or before `as_of`.

    `as_of` is an ISO date string. Comparison is string-wise, which is exact for
    ISO-8601 dates and avoids parsing ~100k values per company.
    """
    out = {k: v for k, v in raw.items() if k != "facts"}
    out["facts"] = {}
    for taxonomy, tags in raw.get("facts", {}).items():
        kept_tags = {}
        for tag, body in tags.items():
            kept_units = {}
            for unit, facts in body.get("units", {}).items():
                kept = [f for f in facts
                        if f.get("filed") and f["filed"] <= as_of]
                if kept:
                    kept_units[unit] = kept
            if kept_units:
                new_body = {k: v for k, v in body.items() if k != "units"}
                new_body["units"] = kept_units
                kept_tags[tag] = new_body
        if kept_tags:
            out["facts"][taxonomy] = kept_tags
    return out


def fact_census(raw: dict) -> dict:
    """Counts used to prove a filter actually did something (rule 13)."""
    tags = 0
    facts = 0
    latest_filed = None
    for tags_block in raw.get("facts", {}).values():
        for body in tags_block.values():
            tags += 1
            for unit_facts in body.get("units", {}).values():
                facts += len(unit_facts)
                for f in unit_facts:
                    filed = f.get("filed")
                    if filed and (latest_filed is None or filed > latest_filed):
                        latest_filed = filed
    return {"tags": tags, "facts": facts, "latest_filed": latest_filed}


def undated_facts(raw: dict) -> int:
    """Facts carrying no `filed` date — dropped by the filter, counted here so
    the drop is visible rather than silent."""
    n = 0
    for tags_block in raw.get("facts", {}).values():
        for body in tags_block.values():
            for unit_facts in body.get("units", {}).values():
                n += sum(1 for f in unit_facts if not f.get("filed"))
    return n


def as_of_for_event(event_date: str, lead_days: int = 365) -> str:
    """The cutoff for an event: `lead_days` before it, as an ISO date."""
    from datetime import date, timedelta
    return (date.fromisoformat(event_date) - timedelta(days=lead_days)).isoformat()


def deepcopy_payload(raw: dict) -> dict:
    return copy.deepcopy(raw)
