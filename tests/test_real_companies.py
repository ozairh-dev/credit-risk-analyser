"""The regression net: the real pipeline over every cached filing.

Every other test runs against the hand-built fixture or small synthetic dicts.
That is how the D29 fact-identity bug survived — a crash on data sitting in
data/raw/ that no test touched (pre-Task-9 audit, finding 2).

This module runs select -> map -> store over each cached companyfacts file and
asserts properties rather than pinned magic numbers: that storing succeeds, that
what the store holds matches what selection and mapping produced, and that
re-storing the same filings changes nothing. Pinned counts would be re-derived
from the code they are meant to police, and would need re-baselining on every
legitimate tag-map change.

Skips cleanly when data/raw/ is absent, so a fresh checkout still passes — the
cache is gitignored.
"""

import json
from pathlib import Path

import pytest

from credit_risk import config
from credit_risk.normalise import map_concepts, select_annual_facts
from credit_risk.normalise.selection import period_type
from credit_risk.store import db, queries
from credit_risk.store.writer import store_company_data

CACHED = sorted((config.RAW_DIR).glob("CIK*.json")) if config.RAW_DIR.exists() else []

pytestmark = pytest.mark.skipif(
    not CACHED, reason="no cached companyfacts in data/raw/ (gitignored)"
)


def load(path):
    return json.loads(path.read_text())["content"]


@pytest.fixture(params=CACHED, ids=lambda p: p.stem)
def company(request):
    """One cached company, run through selection and mapping."""
    raw = load(request.param)
    selection = select_annual_facts(raw)
    return raw, selection, map_concepts(selection)


@pytest.fixture
def stored(company):
    raw, selection, mapping = company
    conn = db.create_database(":memory:")
    store_company_data(
        conn, raw["cik"], raw["entityName"], selection, mapping,
        tag_map=config.tag_map(),
    )
    yield conn, raw, selection, mapping
    conn.close()


def scalar(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()[0]


def test_stores_without_raising(stored):
    """The headline invariant: every cached filing history is storable.

    KHC failed this before D29 — `superseding fact not found` — and nothing in
    the suite noticed.
    """
    conn, raw, _, _ = stored
    assert scalar(conn, "SELECT COUNT(*) FROM companies WHERE cik=?", (raw["cik"],)) == 1
    assert scalar(conn, "SELECT COUNT(*) FROM facts") > 0


def test_stored_facts_match_what_selection_produced(stored):
    """Counts are checked against selection's own output, not pinned numbers."""
    conn, _, selection, _ = stored
    for status, bucket in [
        ("CURRENT", selection.selected),
        ("SUPERSEDED", selection.superseded),
        ("DUPLICATE", selection.duplicates),
        ("UNAVAILABLE", selection.unavailable),
    ]:
        assert scalar(
            conn, "SELECT COUNT(*) FROM facts WHERE status=?", (status,)
        ) == len(bucket), status


def test_stored_concepts_and_events_match_mapping(stored):
    conn, cik_raw, selection, mapping = stored
    assert scalar(conn, "SELECT COUNT(*) FROM concepts") == (
        len(mapping.concepts) + len(mapping.unavailable)
    )
    assert scalar(conn, "SELECT COUNT(*) FROM concepts WHERE data_status='REPORTED'") == (
        len(mapping.concepts)
    )
    expected_events = len(selection.warnings) + len(mapping.warnings)
    assert scalar(conn, "SELECT COUNT(*) FROM data_quality_events") == expected_events


def test_no_fact_is_superseded_by_its_own_filing(stored):
    """The D29 symptom, asserted directly: supersession crosses filings."""
    conn, _, _, _ = stored
    assert scalar(conn, """
        SELECT COUNT(*) FROM facts old JOIN facts new
          ON new.id = old.superseded_by_fact_id
        WHERE old.accession = new.accession
    """) == 0


def test_superseded_facts_keep_their_period_type(stored):
    """A supersession must never pair a duration fact with an instant one (D29)."""
    conn, _, _, _ = stored
    assert scalar(conn, """
        SELECT COUNT(*) FROM facts old JOIN facts new
          ON new.id = old.superseded_by_fact_id
        WHERE (old.period_start IS NULL) <> (new.period_start IS NULL)
    """) == 0


def test_every_reported_concept_links_to_a_matching_fact(stored):
    """Provenance integrity: a REPORTED concept points at a CURRENT fact with the
    same tag, period end AND period type."""
    conn, _, _, _ = stored
    assert scalar(conn, """
        SELECT COUNT(*) FROM concepts c
        JOIN facts f ON f.id = c.fact_id
        WHERE c.data_status='REPORTED'
          AND (f.tag <> c.source_tag
               OR f.period_end <> c.period_end
               OR (f.period_start IS NULL) <> (c.period_start IS NULL)
               OR f.status <> 'CURRENT')
    """) == 0
    assert scalar(
        conn, "SELECT COUNT(*) FROM concepts WHERE data_status='REPORTED' AND fact_id IS NULL"
    ) == 0


def test_restoring_is_idempotent(stored):
    """Re-ingesting unchanged filings must add nothing (D18b)."""
    conn, raw, selection, mapping = stored
    before = {
        table: scalar(conn, f"SELECT COUNT(*) FROM {table}")
        for table in ("facts", "concepts", "filings", "data_quality_events")
    }
    store_company_data(
        conn, raw["cik"], raw["entityName"], selection, mapping,
        tag_map=config.tag_map(),
    )
    after = {
        table: scalar(conn, f"SELECT COUNT(*) FROM {table}")
        for table in ("facts", "concepts", "filings", "data_quality_events")
    }
    assert after == before
    assert scalar(conn, "SELECT COUNT(*) FROM concepts WHERE status='SUPERSEDED'") == 0


def test_application_queries_run_on_real_data(stored):
    """Q1-Q3 from the Task 8 design, exercised against a real filing history."""
    conn, raw, _, mapping = stored
    cik = raw["cik"]
    assert len(queries.concepts_with_provenance(conn, cik)) == (
        len(mapping.concepts) + len(mapping.unavailable)
    )
    summary = queries.data_quality_by_period(conn, cik)
    assert summary, "every cached company has at least one period"
    for row in summary:
        assert row["reported"] + row["missing"] == len(config.tag_map())
    for row in queries.restatements(conn, cik):
        assert row["original_value"] != row["current_value"]  # D15


def test_fixture_shapes_are_actually_present_somewhere(stored):
    """Guards against the net passing vacuously: across the cached set the
    interesting buckets must be non-empty, or these assertions prove nothing."""
    conn, _, selection, _ = stored
    observed = {
        "duplicates": len(selection.duplicates),
        "superseded": len(selection.superseded),
        "durations": sum(1 for f in selection.selected if period_type(f) == "duration"),
        "instants": sum(1 for f in selection.selected if period_type(f) == "instant"),
    }
    assert all(n > 0 for n in observed.values()), observed
