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

Q_DATA_QUALITY_BY_PERIOD = """
SELECT period_end,
       SUM(data_status = 'REPORTED')    AS reported,
       SUM(data_status = 'UNAVAILABLE') AS missing,
       SUM(COALESCE(source_tag_rank, 0) > 0) AS fallbacks_used
FROM concepts
WHERE cik = ? AND status = 'CURRENT'
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
