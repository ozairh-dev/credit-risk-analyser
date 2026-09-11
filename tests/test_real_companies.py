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
from credit_risk.metrics.composites import compute_composites
from credit_risk.metrics.integrity import run_integrity_checks
from credit_risk.metrics.ratios import EVIDENCE, GAP, compute_metrics, reason_kind
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
    composites = compute_composites(mapping)
    store_company_data(
        conn, raw["cik"], raw["entityName"], selection, mapping,
        tag_map=config.tag_map(), composites=composites,
        integrity=run_integrity_checks(mapping, composites),
        metrics=compute_metrics(mapping, composites),
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
    comps = compute_composites(mapping)
    filled = {(c.concept, c.end) for c in comps}
    unfilled = [u for u in mapping.unavailable
                if (u.concept, u.period_end) not in filled]
    assert scalar(conn, "SELECT COUNT(*) FROM concepts") == (
        len(mapping.concepts) + len(unfilled) + len(comps)
    )
    assert scalar(conn, "SELECT COUNT(*) FROM concepts WHERE data_status='REPORTED'") == (
        len(mapping.concepts)
    )
    # abnormal-movement flags are events too (D23/D37), so the expectation
    # includes them now that integrity runs in the stored fixture
    integrity = run_integrity_checks(mapping, comps)
    expected_events = (len(selection.warnings) + len(mapping.warnings)
                       + len(integrity.events))
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
        tag_map=config.tag_map(), composites=compute_composites(mapping),
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
    comps = compute_composites(mapping)
    filled = {(c.concept, c.end) for c in comps}
    unfilled = [u for u in mapping.unavailable
                if (u.concept, u.period_end) not in filled]
    assert len(queries.concepts_with_provenance(conn, cik)) == (
        len(mapping.concepts) + len(unfilled) + len(comps)
    )
    summary = queries.data_quality_by_period(conn, cik)
    assert summary, "every cached company has at least one period"
    # a period where gross_profit was filled by the calculated fallback has
    # that concept as CALCULATED — neither "reported" nor "missing"; the
    # panel's fuller treatment of calculated fallbacks is Task 10's job
    gp_filled = {c.end for c in comps if c.concept == "gross_profit"}
    for row in summary:
        expected = len(config.tag_map()) - (1 if row["period_end"] in gp_filled else 0)
        assert row["reported"] + row["missing"] == expected
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


# ============ Task 9: composite branches on real data ============
#
# These figures are pinned, not derived: each was measured on 2026-09-11 and
# cross-checked against the figures D26 and D27 recorded when those decisions
# were made. If a tag-map or methodology change legitimately moves one, the
# decision record is what says whether the move is right.

BRANCHES = {
    # cik: (methods per branch, refusals per reason)
    18926: ({"debt_from_lease_inclusive_ltd": 15},
            {"NO_DEBT_DATA": 2, "COMPONENT_AGGREGATE_MISMATCH": 2}),        # LUMN
    37996: ({"debt_from_components": 3}, {"NO_DEBT_DATA": 16}),             # F
    200406: ({"debt_from_components": 18}, {"NO_DEBT_DATA": 1}),            # JNJ
    815097: ({"debt_from_components": 17},
             {"NO_DEBT_DATA": 1, "COMPONENT_AGGREGATE_MISMATCH": 1}),       # CCL
    1637459: ({"debt_from_lease_inclusive_ltd": 12}, {"NO_DEBT_DATA": 1}),  # KHC
}

MISMATCHES = {
    # (cik, period_end): fragment the refusal detail must contain — the two
    # figures and the deviation D26/D27 documented
    (18926, "2009-12-31"): "93.6%",     # 500M vs 7,754M (D27's LUMN 2009)
    (18926, "2010-12-31"): "99.8%",     # 12M vs 7,328M
    (815097, "2010-11-30"): "7.9%",     # 8,624M vs 9,364M (D26's CCL case)
}


def test_total_debt_branch_per_company(stored):
    conn, raw, _, _ = stored
    methods = dict(conn.execute(
        """SELECT method, COUNT(*) FROM concepts
           WHERE concept='total_debt' AND status='CURRENT'
             AND data_status='CALCULATED' GROUP BY method"""
    ).fetchall())
    refusals = dict(conn.execute(
        """SELECT reason_code, COUNT(*) FROM concepts
           WHERE concept='total_debt' AND status='CURRENT'
             AND data_status='UNAVAILABLE' GROUP BY reason_code"""
    ).fetchall())
    want_methods, want_refusals = BRANCHES[raw["cik"]]
    assert methods == want_methods
    assert refusals == want_refusals


def test_mismatch_refusals_record_the_documented_deviations(stored):
    conn, raw, _, _ = stored
    rows = conn.execute(
        """SELECT period_end, detail FROM concepts
           WHERE concept='total_debt' AND status='CURRENT'
             AND reason_code='COMPONENT_AGGREGATE_MISMATCH'"""
    ).fetchall()
    expected = {end: frag for (cik, end), frag in MISMATCHES.items()
                if cik == raw["cik"]}
    assert {r["period_end"] for r in rows} == set(expected)
    for r in rows:
        assert expected[r["period_end"]] in r["detail"]


SPOT_VALUES = {
    # (cik, concept, period_end): value — cross-checked against D27's cited
    # bundled figure (LUMN 2019: 34,694M) and CCL's D25 debt arc
    (18926, "total_debt", "2019-12-31"): 34_694_000_000,
    (815097, "total_debt", "2011-11-30"): 9_353_000_000,
    (815097, "total_debt", "2025-11-30"): 27_993_000_000,
    (200406, "total_debt", "2025-12-28"): 49_933_000_000,
    (18926, "net_debt", "2019-12-31"): 33_004_000_000,
    (18926, "ebitda", "2019-12-31"): 2_103_000_000,
}


def test_composite_spot_values(stored):
    conn, raw, _, _ = stored
    for (cik, concept, end), value in SPOT_VALUES.items():
        if cik != raw["cik"]:
            continue
        row = conn.execute(
            """SELECT value FROM concepts
               WHERE concept=? AND period_end=? AND status='CURRENT'""",
            (concept, end),
        ).fetchone()
        assert row is not None and row["value"] == value, (concept, end)


def test_lease_inclusive_branch_refuses_ex_leases(stored):
    """Every lease-inclusive period must pair with LEASES_NOT_SEPARABLE (D27)."""
    conn, raw, _, _ = stored
    n_branch = scalar(conn, """SELECT COUNT(*) FROM concepts
        WHERE concept='total_debt' AND status='CURRENT'
          AND method='debt_from_lease_inclusive_ltd'""")
    n_refused = scalar(conn, """SELECT COUNT(*) FROM concepts
        WHERE concept='total_debt_ex_leases' AND status='CURRENT'
          AND reason_code='LEASES_NOT_SEPARABLE'""")
    assert n_branch == n_refused


def test_composites_link_their_inputs(stored):
    """Every CALCULATED composite has concept_inputs provenance and no accession."""
    conn, raw, _, _ = stored
    rows = conn.execute(
        """SELECT c.id, c.accession, COUNT(ci.input_concept_id) AS n_inputs
           FROM concepts c LEFT JOIN concept_inputs ci ON ci.concept_id = c.id
           WHERE c.data_status='CALCULATED' AND c.status='CURRENT'
           GROUP BY c.id"""
    ).fetchall()
    assert rows, "no CALCULATED composites stored"
    for r in rows:
        assert r["accession"] is None
        assert r["n_inputs"] >= 1


def test_composite_restore_is_idempotent_on_real_data(stored):
    conn, raw, selection, mapping = stored
    before = scalar(conn, "SELECT COUNT(*) FROM concepts")
    store_company_data(
        conn, raw["cik"], raw["entityName"], selection, mapping,
        tag_map=config.tag_map(), composites=compute_composites(mapping),
    )
    assert scalar(conn, "SELECT COUNT(*) FROM concepts") == before


# ============ Task 10: integrity checks on real data ============
#
# Measured 2026-09-11. Outcome counts are pinned because they are the witness
# evidence: a SKIP count is how thin a check's real-data coverage is, and a
# silent change in it would be a coverage regression no other test would see.

INTEGRITY_OUTCOMES = {
    # cik: {outcome: count} across all checks and periods
    18926: {"PASS": 69, "SKIP": 64},                       # LUMN
    37996: {"PASS": 91, "SKIP": 42},                       # F
    200406: {"PASS": 118, "SKIP": 15},                     # JNJ
    815097: {"PASS": 69, "SKIP": 64},                      # CCL
    1637459: {"PASS": 57, "SKIP": 32, "WARN": 2},          # KHC
}

# The only non-PASS outcomes in the entire cached set, and both are genuine:
# Kraft Heinz's pre-merger (2014) and merger-year (2015) balance sheets do not
# close against the mapped `equity` tag. The methodology warns rather than
# rejects here precisely because minority-interest presentation varies.
INTEGRITY_WARNINGS = {
    (1637459, "2014-12-28", "balance_sheet_balances"): 0.2343,
    (1637459, "2016-01-03", "balance_sheet_balances"): 0.0695,
}


def test_integrity_outcome_counts(stored):
    conn, raw, _, _ = stored
    counts = dict(conn.execute(
        """SELECT outcome, COUNT(*) FROM integrity_results
           WHERE cik = ? GROUP BY outcome""", (raw["cik"],)
    ).fetchall())
    assert counts == INTEGRITY_OUTCOMES[raw["cik"]]


def test_no_cached_company_fails_an_integrity_check(stored):
    """No FAIL anywhere in the cached set — asserted so a future tag-map or
    methodology change that starts failing real filings is loud, not silent."""
    conn, raw, _, _ = stored
    assert scalar(conn, """SELECT COUNT(*) FROM integrity_results
        WHERE cik = ? AND outcome = 'FAIL'""", (raw["cik"],)) == 0


def test_integrity_warnings_are_the_documented_ones(stored):
    conn, raw, _, _ = stored
    rows = conn.execute(
        """SELECT period_end, check_name, deviation FROM integrity_results
           WHERE cik = ? AND outcome = 'WARN'""", (raw["cik"],)
    ).fetchall()
    expected = {(e, c): d for (cik, e, c), d in INTEGRITY_WARNINGS.items()
                if cik == raw["cik"]}
    assert {(r["period_end"], r["check_name"]) for r in rows} == set(expected)
    for r in rows:
        assert r["deviation"] == pytest.approx(
            expected[(r["period_end"], r["check_name"])], abs=0.0001)


def test_continuity_never_warns_on_any_cached_company(stored):
    """D36 and D40 together, on real data: 52/53-week fiscal calendars and
    phantom periods each used to produce false gaps. Every cached company's
    filing history is in fact continuous."""
    conn, raw, _, _ = stored
    assert scalar(conn, """SELECT COUNT(*) FROM integrity_results
        WHERE cik = ? AND check_name = 'period_continuity'
          AND outcome = 'WARN'""", (raw["cik"],)) == 0


def test_phantom_periods_are_recorded_not_hidden(stored):
    """LUMN 2014-02-20 and KHC 2013-04-28 (D40): every check skips, and the
    continuity skip says why."""
    conn, raw, _, mapping = stored
    with_values = {c.end for c in mapping.concepts}
    phantoms = {u.period_end for u in mapping.unavailable} - with_values
    for end in phantoms:
        outcomes = {r["outcome"] for r in conn.execute(
            """SELECT outcome FROM integrity_results
               WHERE cik = ? AND period_end = ?""", (raw["cik"], end))}
        assert outcomes == {"SKIP"}
        detail = conn.execute(
            """SELECT detail FROM integrity_results WHERE cik = ? AND period_end = ?
               AND check_name = 'period_continuity'""", (raw["cik"], end)
        ).fetchone()["detail"]
        assert "not a trend period" in detail


def test_period_verdict_is_derived_consistently(stored):
    """The query derivation (D37) must agree with the module's function."""
    conn, raw, _, _ = stored
    from collections import defaultdict
    by_period = defaultdict(list)
    for r in conn.execute(
        """SELECT period_end, outcome FROM integrity_results WHERE cik = ?""",
        (raw["cik"],)
    ):
        by_period[r["period_end"]].append(r["outcome"])
    derived = {r["period_end"]: r["verdict"]
               for r in queries.integrity_verdict_by_period(conn, raw["cik"])}
    for end, outcomes in by_period.items():
        want = ("FAIL" if "FAIL" in outcomes
                else "WARN" if "WARN" in outcomes else "PASS")
        assert derived[end] == want


def test_data_quality_summary_separates_the_four_kinds_of_absence(stored):
    """A refused composite and a never-resolved concept are different things
    and must not be summed together (Task 10)."""
    conn, raw, _, _ = stored
    rows = queries.data_quality_by_period(conn, raw["cik"])
    assert rows
    for row in rows:
        total = (row["reported"] + row["calculated"] + row["missing"]
                 + row["refused_composites"])
        stored_here = scalar(conn, """SELECT COUNT(*) FROM concepts
            WHERE cik = ? AND period_end = ? AND status = 'CURRENT'""",
            (raw["cik"], row["period_end"]))
        assert total == stored_here
        assert row["fallbacks_used"] <= row["reported"]


def test_integrity_restore_is_idempotent(stored):
    """The (cik, period_end, check) key means a re-run updates (D37)."""
    conn, raw, selection, mapping = stored
    before = scalar(conn, "SELECT COUNT(*) FROM integrity_results")
    composites = compute_composites(mapping)
    store_company_data(
        conn, raw["cik"], raw["entityName"], selection, mapping,
        tag_map=config.tag_map(), composites=composites,
        integrity=run_integrity_checks(mapping, composites),
    )
    assert scalar(conn, "SELECT COUNT(*) FROM integrity_results") == before


# ============ Task 11: the three ratios on real data ============
#
# Every count below was measured, reconciled against the company's period
# count, and spot-checked by hand before being pinned (CLAUDE.md rule 14).
# CCL 2019 was recomputed manually end to end: ebitda 3,276 + 2,160 = 5,436;
# net_debt 11,502 - 518 = 10,984; 10,984 / 5,436 = 2.0206.

METRIC_OUTCOMES = {
    (18926, "net_debt_to_ebitda"): {"value": 14, "MISSING_INPUT:net_debt": 4,
                                    "NEGATIVE_EBITDA": 1},
    (18926, "ebit_interest_cover"): {"value": 15, "NEGATIVE_EARNINGS": 3,
                                     "MISSING_INPUT:total_debt": 1},
    (18926, "current_ratio"): {"value": 17, "MISSING_INPUT:current_assets": 2},

    (37996, "net_debt_to_ebitda"): {"value": 3, "MISSING_INPUT:net_debt": 16},
    (37996, "ebit_interest_cover"): {"value": 7, "MISSING_INPUT:ebit": 10,
                                     "NEGATIVE_EARNINGS": 2},
    (37996, "current_ratio"): {"value": 11, "MISSING_INPUT:current_assets": 8},

    (200406, "net_debt_to_ebitda"): {"value": 6, "MISSING_INPUT:ebitda": 12,
                                     "MISSING_INPUT:net_debt": 1},
    (200406, "ebit_interest_cover"): {"value": 6, "MISSING_INPUT:ebit": 13},
    (200406, "current_ratio"): {"value": 18, "MISSING_INPUT:current_assets": 1},

    (815097, "net_debt_to_ebitda"): {"value": 14, "NEGATIVE_EBITDA": 3,
                                     "MISSING_INPUT:net_debt": 2},
    (815097, "ebit_interest_cover"): {"value": 16, "NEGATIVE_EARNINGS": 3},
    (815097, "current_ratio"): {"value": 18, "MISSING_INPUT:current_assets": 1},

    (1637459, "net_debt_to_ebitda"): {"value": 10, "NEGATIVE_EBITDA": 2,
                                      "MISSING_INPUT:net_debt": 1},
    (1637459, "ebit_interest_cover"): {"value": 10, "NEGATIVE_EARNINGS": 2,
                                       "MISSING_INPUT:total_debt": 1},
    (1637459, "current_ratio"): {"value": 12, "MISSING_INPUT:current_assets": 1},
}

METRIC_SPOT_VALUES = {
    (815097, "net_debt_to_ebitda", "2019-11-30"): 2.0206,
    (815097, "ebit_interest_cover", "2019-11-30"): 15.9029,
    (815097, "current_ratio", "2019-11-30"): 0.2256,
    (18926, "net_debt_to_ebitda", "2019-12-31"): 15.6938,   # 33,004 / 2,103
}


def test_metric_outcome_counts(stored):
    conn, raw, _, _ = stored
    for (cik, metric), expected in METRIC_OUTCOMES.items():
        if cik != raw["cik"]:
            continue
        rows = conn.execute(
            """SELECT data_status, reason_code, COUNT(*) AS n FROM metrics
               WHERE cik = ? AND metric = ? AND status = 'CURRENT'
               GROUP BY data_status, reason_code""", (cik, metric)
        ).fetchall()
        got = {("value" if r["data_status"] == "CALCULATED" else r["reason_code"]):
               r["n"] for r in rows}
        assert got == expected, metric


def test_every_period_has_a_row_for_every_metric(stored):
    """The counts above must reconcile: no period silently skipped."""
    conn, raw, _, _ = stored
    periods = scalar(conn, """SELECT COUNT(DISTINCT period_end) FROM concepts
        WHERE cik = ? AND status = 'CURRENT'""", (raw["cik"],))
    for metric in ("net_debt_to_ebitda", "ebit_interest_cover", "current_ratio"):
        n = scalar(conn, """SELECT COUNT(*) FROM metrics
            WHERE cik = ? AND metric = ? AND status = 'CURRENT'""",
            (raw["cik"], metric))
        assert n == periods, metric


def test_metric_spot_values(stored):
    conn, raw, _, _ = stored
    for (cik, metric, end), value in METRIC_SPOT_VALUES.items():
        if cik != raw["cik"]:
            continue
        row = conn.execute(
            """SELECT value FROM metrics WHERE cik = ? AND metric = ?
               AND period_end = ? AND status = 'CURRENT'""", (cik, metric, end)
        ).fetchone()
        assert row is not None and row["value"] == pytest.approx(value, abs=0.0001)


def test_evidence_reasons_are_only_the_two_expected_codes(stored):
    """D9's split on real data: every EVIDENCE refusal is a real loss, never a
    data gap dressed up as one."""
    conn, raw, _, _ = stored
    rows = conn.execute(
        """SELECT DISTINCT reason_code FROM metrics
           WHERE cik = ? AND status = 'CURRENT' AND data_status = 'UNAVAILABLE'""",
        (raw["cik"],)
    ).fetchall()
    for r in rows:
        kind = reason_kind(r["reason_code"])
        assert kind in (EVIDENCE, GAP)
        if kind == EVIDENCE:
            assert r["reason_code"] in ("NEGATIVE_EBITDA", "NEGATIVE_EARNINGS")


def test_calculated_metrics_link_their_inputs(stored):
    """Every computed ratio has metric_inputs provenance and no accession."""
    conn, raw, _, _ = stored
    rows = conn.execute(
        """SELECT m.id, m.accession, COUNT(mi.concept_id) AS n
           FROM metrics m LEFT JOIN metric_inputs mi ON mi.metric_id = m.id
           WHERE m.cik = ? AND m.status = 'CURRENT'
             AND m.data_status = 'CALCULATED'
           GROUP BY m.id""", (raw["cik"],)
    ).fetchall()
    assert rows
    for r in rows:
        assert r["accession"] is None
        assert r["n"] == 2          # all three ratios take exactly two inputs


def test_metric_provenance_reaches_a_filing(stored):
    """The deliverable: a ratio traces to tags and filings (Task 11)."""
    conn, raw, _, _ = stored
    end = conn.execute(
        """SELECT period_end FROM metrics WHERE cik = ? AND status = 'CURRENT'
           AND data_status = 'CALCULATED' ORDER BY period_end DESC LIMIT 1""",
        (raw["cik"],)
    ).fetchone()["period_end"]
    rows = queries.metric_provenance(conn, raw["cik"], end)
    assert rows
    # the tag may sit on the input concept itself (a REPORTED input) or on a
    # concept one level down (a composite input) — either reaches a filing
    assert any(r["accession"] and (r["source_tag"] or r["input_tag"])
               for r in rows)


def test_metrics_restore_is_idempotent(stored):
    conn, raw, selection, mapping = stored
    before = scalar(conn, "SELECT COUNT(*) FROM metrics")
    composites = compute_composites(mapping)
    store_company_data(
        conn, raw["cik"], raw["entityName"], selection, mapping,
        tag_map=config.tag_map(), composites=composites,
        integrity=run_integrity_checks(mapping, composites),
        metrics=compute_metrics(mapping, composites),
    )
    assert scalar(conn, "SELECT COUNT(*) FROM metrics") == before
    assert scalar(conn, "SELECT COUNT(*) FROM metrics WHERE status='SUPERSEDED'") == 0
