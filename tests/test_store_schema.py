"""Task 8: the schema enforces its own rules.

Constraint tests attempt the ILLEGAL case and assert the database rejects it —
a test that only stores legal rows would pass against a schema with no
constraints at all.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from credit_risk.normalise import map_concepts, select_annual_facts
from credit_risk.store import db, queries, schema
from credit_risk.store.fingerprint import (
    COMPOSITE_DEFAULTS,
    composite_config_values,
    config_fingerprint,
)
from credit_risk.store.writer import store_company_data

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "companyfacts_minimal.json"
CIK = 999999
A22 = "0000999999-23-000001"
A23 = "0000999999-24-000001"


@pytest.fixture
def conn():
    c = db.create_database(":memory:")
    yield c
    c.close()


@pytest.fixture
def seeded(conn):
    """A company, a filing and one CURRENT fact — enough to satisfy FKs."""
    conn.execute("INSERT INTO companies (cik, name) VALUES (?,?)", (CIK, "Fixture Co"))
    conn.execute(
        "INSERT INTO filings (accession, cik, form, filed) VALUES (?,?,?,?)",
        (A22, CIK, "10-K", "2023-02-15"),
    )
    conn.execute(
        """INSERT INTO facts (cik, accession, tag, unit, val, period_end, status)
           VALUES (?,?,?,?,?,?, 'CURRENT')""",
        (CIK, A22, "Revenues", "USD", 1000, "2022-12-31"),
    )
    conn.commit()
    return conn


# ============ foreign keys and STRICT ============

def test_foreign_keys_pragma_is_on(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_foreign_key_violation_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO filings (accession, cik, form, filed) VALUES (?,?,?,?)",
            ("x-1", 123456, "10-K", "2023-02-15"),   # no such company
        )


def test_strict_applied_when_supported():
    ddl = schema.ddl_statements(strict=True)
    assert all("STRICT" in s for s in ddl if s.startswith("CREATE TABLE"))
    if schema.SUPPORTS_STRICT:
        assert "STRICT" in schema.ddl_statements()[0]


def test_non_strict_fallback_path_creates_schema():
    ddl = schema.ddl_statements(strict=False)
    assert not any("STRICT" in s for s in ddl)
    c = db.connect(":memory:")
    schema.create_schema(c, strict=False)          # must not raise
    assert c.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 0
    c.close()


@pytest.mark.skipif(not schema.SUPPORTS_STRICT, reason="SQLite < 3.37")
def test_strict_rejects_wrong_type(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        seeded.execute(
            "INSERT INTO companies (cik, name) VALUES (?,?)", ("not-an-int", "X")
        )


# ============ data_status: six values, enforced in the database ============

@pytest.mark.parametrize("table,extra_cols,extra_vals", [
    ("concepts", ", config_fingerprint, created_at", ", 'fp', 'now'"),
    ("metrics", ", config_fingerprint, created_at", ", 'fp', 'now'"),
])
def test_data_status_rejects_seventh_value(seeded, table, extra_cols, extra_vals):
    key = "concept" if table == "concepts" else "metric"
    with pytest.raises(sqlite3.IntegrityError):
        seeded.execute(
            f"INSERT INTO {table} (cik, {key}, period_end, data_status{extra_cols}) "
            f"VALUES (?,?,?, 'GUESSED'{extra_vals})",
            (CIK, "revenue", "2022-12-31"),
        )


@pytest.mark.parametrize("status", [
    "REPORTED", "CALCULATED", "ESTIMATED", "ASSUMED", "AI_INTERPRETED", "UNAVAILABLE",
])
def test_all_six_data_statuses_accepted(seeded, status):
    fact_id = seeded.execute("SELECT id FROM facts").fetchone()["id"]
    seeded.execute(
        """INSERT INTO concepts (cik, concept, period_end, value, data_status,
                                 source_tag, fact_id, method, reason_code,
                                 config_fingerprint, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,'fp','now')""",
        (
            CIK, f"c_{status}", "2022-12-31",
            None if status == "UNAVAILABLE" else 1.0,
            status,
            "Revenues" if status == "REPORTED" else None,
            fact_id if status == "REPORTED" else None,
            "m_v1" if status == "CALCULATED" else None,
            "NO_CANDIDATE_TAG" if status == "UNAVAILABLE" else None,
        ),
    )


# ============ facts CHECK constraints ============

def insert_fact(conn, **kw):
    cols = {"cik": CIK, "accession": A22, "tag": "T", "unit": "USD",
            "period_end": "2022-12-31", "status": "CURRENT"}
    cols.update(kw)
    names = ", ".join(cols)
    marks = ", ".join("?" * len(cols))
    return conn.execute(f"INSERT INTO facts ({names}) VALUES ({marks})",
                        tuple(cols.values()))


def test_facts_status_constrained(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(seeded, status="BOGUS")


def test_superseded_fact_must_name_its_superseder(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(seeded, tag="X", status="SUPERSEDED")      # no pointer


def test_non_superseded_fact_must_not_name_a_superseder(seeded):
    target = seeded.execute("SELECT id FROM facts").fetchone()["id"]
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(seeded, tag="X", status="CURRENT", superseded_by_fact_id=target)


def test_unavailable_fact_requires_reason_code(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(seeded, tag="X", status="UNAVAILABLE")     # no reason


def test_available_fact_must_not_carry_reason_code(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(seeded, tag="X", status="CURRENT", reason_code="FOREIGN_UNIT")


def test_unavailable_fact_must_not_carry_a_value(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(seeded, tag="X", status="UNAVAILABLE",
                    reason_code="FOREIGN_UNIT", val=1.0)


def test_only_one_current_fact_per_identity(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(seeded, tag="Revenues", accession=A22)     # duplicate identity


def test_duplicate_status_may_share_identity_with_current(seeded):
    seeded.execute(
        "INSERT INTO filings (accession, cik, form, filed) VALUES (?,?,?,?)",
        (A23, CIK, "10-K", "2024-02-15"),
    )
    insert_fact(seeded, tag="Revenues", accession=A23, status="DUPLICATE", val=1000)


# ============ concepts CHECK constraints ============

def insert_concept(conn, **kw):
    cols = {"cik": CIK, "concept": "revenue", "period_end": "2022-12-31",
            "data_status": "CALCULATED", "method": "m_v1",
            "config_fingerprint": "fp", "created_at": "now"}
    cols.update(kw)
    names = ", ".join(cols)
    marks = ", ".join("?" * len(cols))
    return conn.execute(f"INSERT INTO concepts ({names}) VALUES ({marks})",
                        tuple(cols.values()))


def test_unavailable_concept_requires_reason_code(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        insert_concept(seeded, data_status="UNAVAILABLE", method=None)


def test_available_concept_must_not_carry_reason_code(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        insert_concept(seeded, reason_code="NO_CANDIDATE_TAG")


def test_unavailable_concept_must_not_carry_a_value(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        insert_concept(seeded, data_status="UNAVAILABLE", method=None,
                       reason_code="NO_CANDIDATE_TAG", value=1.0)


def test_reported_concept_requires_source_tag_and_fact(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        insert_concept(seeded, data_status="REPORTED", method=None, value=1.0)


def test_calculated_concept_requires_method(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        insert_concept(seeded, data_status="CALCULATED", method=None, value=1.0)


def test_concept_status_constrained(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        insert_concept(seeded, status="ARCHIVED", value=1.0)


def test_only_one_current_concept_per_identity(seeded):
    insert_concept(seeded, value=1.0)
    with pytest.raises(sqlite3.IntegrityError):
        insert_concept(seeded, value=2.0)


# ============ metrics, assumptions, scores, warnings constraints ============

def test_metric_override_flag_must_match_override_id(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        seeded.execute(
            """INSERT INTO metrics (cik, metric, period_end, data_status, method,
                                    override_applied, config_fingerprint, created_at)
               VALUES (?,?,?, 'CALCULATED', 'm_v1', 1, 'fp', 'now')""",
            (CIK, "current_ratio", "2022-12-31"),
        )


def test_assumption_source_constrained(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        seeded.execute(
            """INSERT INTO assumptions (name, value, source, effective_date)
               VALUES ('fixed_cost_share', '0.3', 'invented', '2026-09-10')"""
        )


@pytest.mark.parametrize("grade,cats", [(0, 5), (7, 5), (3, 6)])
def test_score_ranges_constrained(seeded, grade, cats):
    with pytest.raises(sqlite3.IntegrityError):
        seeded.execute(
            """INSERT INTO scores (cik, period_end, total_score, grade,
                                   categories_available, created_at)
               VALUES (?,?,?,?,?, 'now')""",
            (CIK, "2022-12-31", 60.0, grade, cats),
        )


def test_warning_severity_constrained(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        seeded.execute(
            """INSERT INTO warnings (cik, period_end, indicator, base_severity,
                                     severity, created_at)
               VALUES (?,?,?, 'Medium', 'Critical', 'now')""",
            (CIK, "2022-12-31", "Leverage deterioration"),
        )


def test_score_component_treatment_constrained(seeded):
    seeded.execute(
        """INSERT INTO scores (id, cik, period_end, total_score, grade,
                               categories_available, created_at)
           VALUES (1,?,?,60.0,3,5,'now')""",
        (CIK, "2022-12-31"),
    )
    with pytest.raises(sqlite3.IntegrityError):
        seeded.execute(
            """INSERT INTO score_components (score_id, category, metric, weight,
                                             treatment)
               VALUES (1, 'Leverage', 'net_debt_to_ebitda', 25, 'ignored')"""
        )


# ============ amendment 4: the circular FK actually works ============

def test_circular_fk_create_then_insert_with_fk_enforcement(conn):
    """concepts.override_id -> overrides.id and overrides.concept_id -> concepts.id
    form a cycle. Prove the whole path works with PRAGMA foreign_keys=ON."""
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.execute("INSERT INTO companies (cik, name) VALUES (?,?)", (CIK, "Fixture Co"))
    conn.execute(
        "INSERT INTO filings (accession, cik, form, filed) VALUES (?,?,?,?)",
        (A22, CIK, "10-K", "2023-02-15"),
    )
    conn.execute(
        """INSERT INTO facts (cik, accession, tag, unit, val, period_end, status)
           VALUES (?,?,?,?,?,?, 'CURRENT')""",
        (CIK, A22, "Revenues", "USD", 1000, "2022-12-31"),
    )
    fact_id = conn.execute("SELECT id FROM facts").fetchone()["id"]
    cur = conn.execute(
        """INSERT INTO concepts (cik, concept, period_end, value, data_status,
                                 source_tag, fact_id, config_fingerprint, created_at)
           VALUES (?,?,?,?, 'REPORTED', 'Revenues', ?, 'fp', 'now')""",
        (CIK, "revenue", "2022-12-31", 1000, fact_id),
    )
    concept_id = cur.lastrowid
    cur = conn.execute(
        """INSERT INTO overrides (concept_id, original_value, override_value,
                                  reason, author, created_at)
           VALUES (?,?,?,?,?, 'now')""",
        (concept_id, 1000, 1100, "analyst adjustment", "hamza"),
    )
    override_id = cur.lastrowid
    conn.execute("UPDATE concepts SET override_id=? WHERE id=?", (override_id, concept_id))
    conn.commit()
    row = conn.execute(
        """SELECT c.value, c.override_id, o.original_value, o.override_value
           FROM concepts c JOIN overrides o ON o.id = c.override_id""",
    ).fetchone()
    assert (row["value"], row["original_value"], row["override_value"]) == (1000, 1000, 1100)
    # the original concepts row is untouched (rule 5)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE concepts SET override_id = 9999 WHERE id=?", (concept_id,))


# ============ storing the fixture: the worked example, exactly ============

@pytest.fixture
def stored(conn):
    raw = json.loads(FIXTURE_PATH.read_text())
    selection = select_annual_facts(raw)
    mapping = map_concepts(selection)
    store_company_data(
        conn, CIK, raw["entityName"], selection, mapping,
        tag_map={"cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold"]},
    )
    return conn


def count(conn, table, where="1=1", params=()):
    return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0]


def test_fixture_row_counts(stored):
    assert count(stored, "companies") == 1
    assert count(stored, "filings") == 2          # the 10-Q contributed nothing stored
    assert count(stored, "facts") == 9
    assert count(stored, "facts", "status='CURRENT'") == 7
    assert count(stored, "facts", "status='SUPERSEDED'") == 1
    assert count(stored, "facts", "status='DUPLICATE'") == 1
    assert count(stored, "concepts") == 62
    assert count(stored, "concepts", "data_status='REPORTED'") == 7
    assert count(stored, "concepts", "data_status='UNAVAILABLE'") == 55
    assert count(stored, "data_quality_events") == 0


def test_fixture_facts_exact_set(stored):
    rows = stored.execute(
        "SELECT tag, period_end, val, status, accession FROM facts"
    ).fetchall()
    assert {tuple(r) for r in rows} == {
        ("Revenues", "2022-12-31", 1000, "CURRENT", A22),
        ("Revenues", "2022-12-31", 1000, "DUPLICATE", A23),
        ("Revenues", "2023-12-31", 1200, "CURRENT", A23),
        ("NetIncomeLoss", "2022-12-31", 100, "SUPERSEDED", A22),
        ("NetIncomeLoss", "2022-12-31", 90, "CURRENT", A23),
        ("NetIncomeLoss", "2023-12-31", 110, "CURRENT", A23),
        ("CostOfGoodsAndServicesSold", "2023-12-31", 600, "CURRENT", A23),
        ("CashAndCashEquivalentsAtCarryingValue", "2022-12-31", 50, "CURRENT", A22),
        ("CashAndCashEquivalentsAtCarryingValue", "2023-12-31", 70, "CURRENT", A23),
    }


def test_fy_trap_holds_at_the_storage_layer(stored):
    """Worked-example rows 5 and 6: both fy=2023, different period_end, both
    CURRENT — they coexist because identity is (tag, period_end), not fy."""
    rows = stored.execute(
        """SELECT period_end, val, fy FROM facts
           WHERE tag='NetIncomeLoss' AND status='CURRENT' ORDER BY period_end"""
    ).fetchall()
    assert [(r["period_end"], r["val"], r["fy"]) for r in rows] == [
        ("2022-12-31", 90, 2023),
        ("2023-12-31", 110, 2023),
    ]


def test_fy_is_not_indexed_anywhere(stored):
    """The fy-keyed query must have no index supporting it (D19)."""
    indexes = stored.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
    ).fetchall()
    for row in indexes:
        assert "fy" not in row["sql"].split("(")[-1], row["name"]


def test_supersession_self_join_returns_only_the_restatement(stored):
    rows = queries.restatements(stored, CIK)
    assert [tuple(r) for r in rows] == [
        ("NetIncomeLoss", "2022-12-31", 100, 90, A23)
    ]


def test_fallback_rank_recorded(stored):
    row = stored.execute(
        """SELECT source_tag, source_tag_rank FROM concepts
           WHERE concept='cost_of_revenue' AND data_status='REPORTED'"""
    ).fetchone()
    assert (row["source_tag"], row["source_tag_rank"]) == (
        "CostOfGoodsAndServicesSold", 1,
    )


# ============ the queries the application runs ============

def test_q1_concepts_with_provenance_shape(stored):
    rows = queries.concepts_with_provenance(stored, CIK)
    assert len(rows) == 62
    assert set(rows[0].keys()) == {
        "concept", "period_end", "value", "unit", "data_status",
        "source_tag", "label", "reason_code", "accession", "form", "filed",
    }
    revenue = [r for r in rows if r["concept"] == "revenue" and r["period_end"] == "2022-12-31"]
    assert revenue[0]["value"] == 1000
    assert revenue[0]["source_tag"] == "Revenues"
    assert revenue[0]["form"] == "10-K"


def test_q2_data_quality_summary_shape(stored):
    rows = queries.data_quality_by_period(stored, CIK)
    summary = {r["period_end"]: (r["reported"], r["missing"], r["fallbacks_used"])
               for r in rows}
    assert summary == {
        "2022-12-31": (3, 28, 0),     # revenue, net_income, cash
        "2023-12-31": (4, 27, 1),     # + cost_of_revenue via the fallback tag
    }
    assert queries.event_counts(stored, CIK) == []


# ============ amendment 1: append-with-history ============

def test_recompute_under_changed_config_appends_a_second_row(stored):
    """A concept recomputed under different config produces a new CURRENT row;
    the earlier row stays queryable as SUPERSEDED with its own fingerprint."""
    base_fp = config_fingerprint()
    changed_fp = config_fingerprint({**COMPOSITE_DEFAULTS, "include_operating_leases": False})
    assert base_fp != changed_fp

    fact_id = stored.execute(
        """SELECT id FROM facts WHERE tag='Revenues' AND period_end='2022-12-31'
           AND status='CURRENT'"""
    ).fetchone()["id"]
    stored.execute(
        """UPDATE concepts SET status='SUPERSEDED'
           WHERE cik=? AND concept='revenue' AND period_end='2022-12-31'
             AND status='CURRENT'""",
        (CIK,),
    )
    stored.execute(
        """INSERT INTO concepts (cik, concept, period_end, value, unit, data_status,
                                 source_tag, fact_id, config_fingerprint, created_at)
           VALUES (?,?,?,?, 'USD', 'REPORTED', 'Revenues', ?, ?, 'later')""",
        (CIK, "revenue", "2022-12-31", 1000, fact_id, changed_fp),
    )
    stored.commit()

    history = queries.concept_history(stored, CIK, "revenue", "2022-12-31")
    assert len(history) == 2
    assert [r["status"] for r in history] == ["CURRENT", "SUPERSEDED"] or \
           [r["status"] for r in history] == ["SUPERSEDED", "CURRENT"]
    fingerprints = {r["config_fingerprint"] for r in history}
    assert fingerprints == {base_fp, changed_fp}
    current = [r for r in history if r["status"] == "CURRENT"]
    assert len(current) == 1 and current[0]["config_fingerprint"] == changed_fp


def test_restoring_unchanged_data_is_idempotent(conn):
    """Re-ingesting the same filing under the same config moves no value, so it
    adds no facts and no history rows (D18)."""
    raw = json.loads(FIXTURE_PATH.read_text())
    selection = select_annual_facts(raw)
    mapping = map_concepts(selection)
    store_company_data(conn, CIK, raw["entityName"], selection, mapping)
    store_company_data(conn, CIK, raw["entityName"], selection, mapping)
    assert count(conn, "facts") == 9
    assert count(conn, "concepts") == 62
    assert count(conn, "concepts", "status='CURRENT'") == 62
    assert count(conn, "concepts", "status='SUPERSEDED'") == 0


def test_restoring_under_changed_config_writes_history(conn):
    """Same facts, different config fingerprint -> every concept gets a second
    row and the first stays queryable as SUPERSEDED."""
    raw = json.loads(FIXTURE_PATH.read_text())
    selection = select_annual_facts(raw)
    mapping = map_concepts(selection)
    store_company_data(conn, CIK, raw["entityName"], selection, mapping,
                       fingerprint="fp-leases-on")
    store_company_data(conn, CIK, raw["entityName"], selection, mapping,
                       fingerprint="fp-leases-off")
    assert count(conn, "facts") == 9                     # reported facts unchanged
    assert count(conn, "concepts") == 124
    assert count(conn, "concepts", "status='CURRENT'") == 62
    assert count(conn, "concepts", "status='SUPERSEDED'") == 62
    assert count(conn, "concepts",
                 "status='CURRENT' AND config_fingerprint='fp-leases-off'") == 62


def test_cross_fetch_restatement_raises_rather_than_guessing(conn):
    """A changed value for an identity already stored as CURRENT is out of
    Task 8 scope and must fail loudly, not silently corrupt (rule 9)."""
    raw = json.loads(FIXTURE_PATH.read_text())
    selection = select_annual_facts(raw)
    store_company_data(conn, CIK, raw["entityName"], selection,
                       map_concepts(selection))
    changed = select_annual_facts(raw)
    target = [f for f in changed.selected if f.tag == "Revenues"][0]
    target.accn = "0000999999-25-000001"     # a later filing, different value
    target.val = 1111
    conn.execute(
        "INSERT INTO filings (accession, cik, form, filed) VALUES (?,?,?,?)",
        ("0000999999-25-000001", CIK, "10-K", "2025-02-15"),
    )
    with pytest.raises(ValueError, match="Cross-fetch restatement"):
        store_company_data(conn, CIK, raw["entityName"], changed,
                           map_concepts(changed))


# ============ fingerprint ============

def test_fingerprint_is_stable_and_covers_only_the_allowlist():
    assert config_fingerprint() == config_fingerprint()          # deterministic
    assert set(composite_config_values()) == set(COMPOSITE_DEFAULTS)
    assert config_fingerprint({"include_operating_leases": True}) != \
        config_fingerprint({"include_operating_leases": False})
    # key order must not change the hash
    assert config_fingerprint({"a": 1, "b": 2}) == config_fingerprint({"b": 2, "a": 1})
