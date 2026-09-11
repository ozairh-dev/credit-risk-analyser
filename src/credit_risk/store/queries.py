"""The queries the application actually runs (Task 8 design, section 5).

Kept here so the shapes the schema was designed for are exercised by tests
rather than assumed.
"""

Q_CONCEPTS_WITH_PROVENANCE = """
SELECT c.concept, c.period_end, c.value, c.unit, c.data_status,
       c.source_tag, c.label, c.reason_code,
       f.accession, f.form, f.filed
FROM concepts c
LEFT JOIN filings f ON f.accession = c.accession
WHERE c.cik = ? AND c.status = 'CURRENT'
ORDER BY c.concept, c.period_end
"""

# Four kinds of absence, counted separately (Task 10). A composite the engine
# refused is not the same as a concept that never resolved — one is a judgement
# about contradictory data, the other is a tag-map gap — and before this they
# were summed into a single `missing`, so each inflated the other.
#
#   reported          REPORTED concepts (a tag resolved)
#   calculated        CALCULATED values: composites and gross_profit's fallback
#   missing_tags      NO_CANDIDATE_TAG — no candidate tag resolved
#   refused_composites  the engine had inputs and declined to produce a number
#   fallbacks_used    a non-first candidate tag supplied the value
Q_DATA_QUALITY_BY_PERIOD = """
SELECT period_end,
       SUM(data_status = 'REPORTED')   AS reported,
       SUM(data_status = 'CALCULATED') AS calculated,
       SUM(reason_code = 'NO_CANDIDATE_TAG') AS missing,
       SUM(data_status = 'UNAVAILABLE'
           AND reason_code <> 'NO_CANDIDATE_TAG') AS refused_composites,
       SUM(COALESCE(source_tag_rank, 0) > 0) AS fallbacks_used
FROM concepts
WHERE cik = ? AND status = 'CURRENT'
GROUP BY period_end
ORDER BY period_end
"""

Q_MISSING_CONCEPTS = """
SELECT period_end, concept, reason_code
FROM concepts
WHERE cik = ? AND status = 'CURRENT' AND data_status = 'UNAVAILABLE'
ORDER BY period_end, concept
"""

Q_FALLBACK_TAGS_USED = """
SELECT period_end, concept, source_tag, source_tag_rank
FROM concepts
WHERE cik = ? AND status = 'CURRENT' AND COALESCE(source_tag_rank, 0) > 0
ORDER BY period_end, concept
"""

Q_LATEST_FILING = """
SELECT accession, form, filed, fy, fp
FROM filings
WHERE cik = ?
ORDER BY filed DESC, accession DESC
LIMIT 1
"""

Q_INTEGRITY_BY_PERIOD = """
SELECT period_end, check_name, outcome, detail, lhs, rhs, deviation
FROM integrity_results
WHERE cik = ?
ORDER BY period_end, check_name
"""

# The period verdict is DERIVED, never stored (D37): FAIL if any check failed,
# else WARN if any warned, else PASS. SKIP is counted but never decides a
# verdict — a check that could not run is a data gap, not a violation, so a
# period whose checks all skipped is PASS with zero evidence behind it, and
# `checks_run` is what tells the reader that.
Q_INTEGRITY_VERDICT_BY_PERIOD = """
SELECT period_end,
       CASE WHEN SUM(outcome = 'FAIL') > 0 THEN 'FAIL'
            WHEN SUM(outcome = 'WARN') > 0 THEN 'WARN'
            ELSE 'PASS' END AS verdict,
       SUM(outcome = 'PASS') AS passed,
       SUM(outcome = 'WARN') AS warned,
       SUM(outcome = 'FAIL') AS failed,
       SUM(outcome = 'SKIP') AS skipped,
       SUM(outcome <> 'SKIP') AS checks_run
FROM integrity_results
WHERE cik = ?
GROUP BY period_end
ORDER BY period_end
"""

Q_EVENT_COUNTS = """
SELECT code, COUNT(*) AS n
FROM data_quality_events
WHERE cik = ?
GROUP BY code
ORDER BY code
"""

Q_RESTATEMENTS = """
SELECT old.tag, old.period_end,
       old.val AS original_value,
       new.val AS current_value,
       new.accession AS restated_in
FROM facts old
JOIN facts new ON new.id = old.superseded_by_fact_id
WHERE old.cik = ? AND old.status = 'SUPERSEDED'
ORDER BY old.tag, old.period_end
"""

Q_CONCEPT_HISTORY = """
SELECT concept, period_end, value, data_status, status,
       config_fingerprint, created_at
FROM concepts
WHERE cik = ? AND concept = ? AND period_end = ?
ORDER BY created_at, id
"""


def missing_concepts(conn, cik):
    return conn.execute(Q_MISSING_CONCEPTS, (cik,)).fetchall()


def fallback_tags_used(conn, cik):
    return conn.execute(Q_FALLBACK_TAGS_USED, (cik,)).fetchall()


def latest_filing(conn, cik):
    return conn.execute(Q_LATEST_FILING, (cik,)).fetchone()


def integrity_by_period(conn, cik):
    return conn.execute(Q_INTEGRITY_BY_PERIOD, (cik,)).fetchall()


def integrity_verdict_by_period(conn, cik):
    return conn.execute(Q_INTEGRITY_VERDICT_BY_PERIOD, (cik,)).fetchall()


def concepts_with_provenance(conn, cik):
    return conn.execute(Q_CONCEPTS_WITH_PROVENANCE, (cik,)).fetchall()


def data_quality_by_period(conn, cik):
    return conn.execute(Q_DATA_QUALITY_BY_PERIOD, (cik,)).fetchall()


def event_counts(conn, cik):
    return conn.execute(Q_EVENT_COUNTS, (cik,)).fetchall()


def restatements(conn, cik):
    return conn.execute(Q_RESTATEMENTS, (cik,)).fetchall()


def concept_history(conn, cik, concept, period_end):
    return conn.execute(Q_CONCEPT_HISTORY, (cik, concept, period_end)).fetchall()
