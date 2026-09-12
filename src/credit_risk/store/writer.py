"""Persisting selection and mapping output (Task 8).

Facts are stored in full — current, superseded, duplicate and unavailable —
because reported values are never deleted (CLAUDE.md rule 5). Concepts are
append-with-history: an existing CURRENT row for the same identity is flipped
to SUPERSEDED and the new row inserted, so a recompute under different config
leaves both rows queryable (D18).
"""

from datetime import datetime, timezone

from credit_risk.normalise.mapping import MappingResult
from credit_risk.normalise.selection import SelectionResult, period_type
from credit_risk.store.fingerprint import config_fingerprint

FACT_COLUMNS = (
    "cik, accession, tag, label, unit, val, period_start, period_end, "
    "fy, fp, frame, fetched_at, status, superseded_by_fact_id, reason_code"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _upsert_company(conn, cik, name, ticker=None, sic=None) -> None:
    conn.execute(
        """INSERT INTO companies (cik, ticker, name, sic) VALUES (?,?,?,?)
           ON CONFLICT(cik) DO UPDATE SET
             name = excluded.name,
             ticker = COALESCE(excluded.ticker, companies.ticker),
             sic = COALESCE(excluded.sic, companies.sic)""",
        (cik, ticker, name, sic),
    )


def _insert_filings(conn, cik, selection: SelectionResult) -> None:
    seen: dict[str, tuple] = {}
    buckets = (selection.selected, selection.superseded, selection.duplicates)
    for bucket in buckets:
        for f in bucket:
            if f.accn and f.accn not in seen:
                seen[f.accn] = (f.form, f.filed, f.fy, f.fp)
    for u in selection.unavailable:
        if u.accn and u.accn not in seen and u.form and u.filed:
            seen[u.accn] = (u.form, u.filed, None, None)
    for accession, (form, filed, fy, fp) in seen.items():
        conn.execute(
            """INSERT INTO filings (accession, cik, form, filed, fy, fp)
               VALUES (?,?,?,?,?,?) ON CONFLICT(accession) DO NOTHING""",
            (accession, cik, form, filed, fy, fp),
        )


def _insert_fact(conn, cik, f, status, superseded_by_id=None, fetched_at=None) -> int:
    cur = conn.execute(
        f"INSERT INTO facts ({FACT_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            cik, f.accn, f.tag, f.label, f.unit, f.val, f.start, f.end,
            f.fy, f.fp, f.frame, fetched_at, status, superseded_by_id, None,
        ),
    )
    return cur.lastrowid


def _is_instant(f) -> int:
    """Period-type discriminator for fact identity, as stored: 1 = instant.

    Matches the `(period_start IS NULL)` term in uq_facts_current (D29).
    """
    return 1 if f.start is None else 0


def _fact_already_stored(conn, cik, f, status) -> bool:
    """Reported facts are idempotent on their natural key: re-ingesting the same
    filing stores nothing new. A *changed* value for an identity already stored
    as CURRENT is a cross-fetch restatement — nothing drives that flow yet, so
    it raises rather than guessing (CLAUDE.md rule 9).

    Identity includes period type (D29): one filing can report the same tag and
    end date as both a duration and an instant fact, and those are two facts.
    """
    row = conn.execute(
        """SELECT val, status FROM facts
           WHERE cik=? AND tag=? AND period_end=? AND accession=?
             AND (period_start IS NULL) = ?""",
        (cik, f.tag, f.end, f.accn, _is_instant(f)),
    ).fetchone()
    if row is not None:
        return True
    if status == "CURRENT":
        clash = conn.execute(
            """SELECT accession, val FROM facts
               WHERE cik=? AND tag=? AND period_end=? AND status='CURRENT'
                 AND (period_start IS NULL) = ?""",
            (cik, f.tag, f.end, _is_instant(f)),
        ).fetchone()
        if clash is not None:
            raise ValueError(
                f"{f.tag} {f.end} is already stored as CURRENT from "
                f"{clash['accession']} (val={clash['val']}); incoming "
                f"{f.accn} (val={f.val}) would displace it. Cross-fetch "
                f"restatement handling is not implemented (Task 8 scope)."
            )
    return False


def _store_facts(conn, cik, selection: SelectionResult, fetched_at=None) -> None:
    # CURRENT and DUPLICATE rows have no intra-table dependencies
    for f in selection.selected:
        if not _fact_already_stored(conn, cik, f, "CURRENT"):
            _insert_fact(conn, cik, f, "CURRENT", fetched_at=fetched_at)
    for f in selection.duplicates:
        if not _fact_already_stored(conn, cik, f, "DUPLICATE"):
            _insert_fact(conn, cik, f, "DUPLICATE", fetched_at=fetched_at)

    # SUPERSEDED rows point at the fact that displaced them. Inserting
    # latest-filed first means a chain's successor always exists already. The
    # sort key includes accn so same-day refilings are ordered exactly as
    # selection ordered them (D16(4)); reverse=True walks that order backwards.
    for f in sorted(selection.superseded,
                    key=lambda s: (s.filed or "", s.accn or ""), reverse=True):
        if _fact_already_stored(conn, cik, f, "SUPERSEDED"):
            continue
        rows = conn.execute(
            """SELECT id FROM facts
               WHERE cik=? AND tag=? AND period_end=? AND accession=?
                 AND (period_start IS NULL) = ?""",
            (cik, f.tag, f.end, f.superseded_by, _is_instant(f)),
        ).fetchall()
        if len(rows) != 1:
            raise ValueError(
                f"expected exactly one superseding fact for {f.tag} {f.end} "
                f"({period_type(f)}, superseded_by={f.superseded_by}), "
                f"found {len(rows)}"
            )
        _insert_fact(conn, cik, f, "SUPERSEDED", superseded_by_id=rows[0]["id"],
                     fetched_at=fetched_at)

    for u in selection.unavailable:
        existing = conn.execute(
            """SELECT 1 FROM facts
               WHERE cik=? AND tag=? AND period_end IS ? AND accession IS ?
                 AND status='UNAVAILABLE'""",
            (cik, u.tag, u.end, u.accn),
        ).fetchone()
        if existing is not None:
            continue
        conn.execute(
            f"INSERT INTO facts ({FACT_COLUMNS}) "
            f"VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                cik, u.accn, u.tag, None, u.unit, None, None, u.end,
                None, None, None, fetched_at, "UNAVAILABLE", None, u.reason_code,
            ),
        )


def _concept_unchanged(conn, cik, concept, period_end, value, data_status,
                       reason_code, detail, fingerprint) -> bool:
    """True when the CURRENT row already says exactly this.

    Append-with-history exists to preserve the evidence that a value MOVED
    (D18); re-storing an identical row under identical config moves nothing, so
    it is a no-op rather than a new history entry.
    """
    row = conn.execute(
        """SELECT value, data_status, reason_code, detail, config_fingerprint
           FROM concepts
           WHERE cik=? AND concept=? AND period_end=? AND status='CURRENT'""",
        (cik, concept, period_end),
    ).fetchone()
    return row is not None and (
        row["value"] == value
        and row["data_status"] == data_status
        and row["reason_code"] == reason_code
        and row["detail"] == detail
        and row["config_fingerprint"] == fingerprint
    )


def _supersede_current_concept(conn, cik, concept, period_end) -> None:
    conn.execute(
        """UPDATE concepts SET status='SUPERSEDED'
           WHERE cik=? AND concept=? AND period_end=? AND status='CURRENT'""",
        (cik, concept, period_end),
    )


def _store_concepts(conn, cik, mapping: MappingResult, fingerprint, tag_ranks,
                    filled=frozenset()) -> None:
    created_at = _now()
    for c in mapping.concepts:
        if _concept_unchanged(conn, cik, c.concept, c.end, c.value,
                              c.data_status, None, None, fingerprint):
            continue
        # Match the source fact on period type too: with identity widened (D29)
        # a duration and an instant fact can both be CURRENT for one (tag, end),
        # and provenance must point at the one the value actually came from.
        fact = conn.execute(
            """SELECT id FROM facts
               WHERE cik=? AND tag=? AND period_end=? AND status='CURRENT'
                 AND (period_start IS NULL) = ?""",
            (cik, c.source_tag, c.end, _is_instant(c)),
        ).fetchone()
        _supersede_current_concept(conn, cik, c.concept, c.end)
        conn.execute(
            """INSERT INTO concepts
               (cik, concept, period_start, period_end, value, unit, fy, fp,
                data_status, source_tag, source_tag_rank, label, fact_id,
                accession, method, reason_code, status, config_fingerprint,
                created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'CURRENT',?,?)""",
            (
                cik, c.concept, c.start, c.end, c.value, c.unit, c.fy, c.fp,
                c.data_status, c.source_tag,
                tag_ranks.get((c.concept, c.source_tag)), c.label,
                fact["id"] if fact else None, c.accn, None, None,
                fingerprint, created_at,
            ),
        )
    for u in mapping.unavailable:
        # a composite fills this (concept, period) — e.g. gross_profit's
        # calculated fallback — so mapping's NO_CANDIDATE_TAG row must not
        # supersede it on every re-store
        if (u.concept, u.period_end) in filled:
            continue
        if _concept_unchanged(conn, cik, u.concept, u.period_end, None,
                              "UNAVAILABLE", u.reason_code, None, fingerprint):
            continue
        _supersede_current_concept(conn, cik, u.concept, u.period_end)
        conn.execute(
            """INSERT INTO concepts
               (cik, concept, period_end, data_status, reason_code, status,
                config_fingerprint, created_at)
               VALUES (?,?,?,'UNAVAILABLE',?, 'CURRENT',?,?)""",
            (cik, u.concept, u.period_end, u.reason_code, fingerprint, created_at),
        )


def _store_composites(conn, cik, composites, fingerprint) -> None:
    """Store CALCULATED composites and their refusals (Task 9).

    Composite rows carry no accession: their provenance is the input concepts,
    linked through concept_inputs, and pinning a multi-input composite to one
    filing would be arbitrary. Input references are (concept, period_end)
    pairs resolved against CURRENT concept rows — which exist by the time this
    runs, because composites are stored after mapping's concepts.
    """
    created_at = _now()
    for comp in composites:
        if _concept_unchanged(conn, cik, comp.concept, comp.end, comp.value,
                              comp.data_status, comp.reason_code, comp.detail,
                              fingerprint):
            continue
        _supersede_current_concept(conn, cik, comp.concept, comp.end)
        cur = conn.execute(
            """INSERT INTO concepts
               (cik, concept, period_end, value, unit, fy, fp, data_status,
                label, method, reason_code, detail, status,
                config_fingerprint, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'CURRENT',?,?)""",
            (
                cik, comp.concept, comp.end, comp.value,
                comp.unit if comp.data_status == "CALCULATED" else None,
                comp.fy, comp.fp, comp.data_status, comp.label, comp.method,
                comp.reason_code, comp.detail, fingerprint, created_at,
            ),
        )
        composite_id = cur.lastrowid
        for input_concept, input_end in comp.inputs:
            row = conn.execute(
                """SELECT id FROM concepts
                   WHERE cik=? AND concept=? AND period_end=? AND status='CURRENT'""",
                (cik, input_concept, input_end),
            ).fetchone()
            if row is None:
                raise ValueError(
                    f"composite {comp.concept} {comp.end} names input "
                    f"{input_concept} {input_end} but no CURRENT concept row exists"
                )
            conn.execute(
                """INSERT OR IGNORE INTO concept_inputs
                   (concept_id, input_concept_id) VALUES (?,?)""",
                (composite_id, row["id"]),
            )


def _metric_unchanged(conn, cik, metric, period_end, value, data_status,
                      reason_code, fingerprint) -> bool:
    row = conn.execute(
        """SELECT value, data_status, reason_code, config_fingerprint
           FROM metrics
           WHERE cik=? AND metric=? AND period_end=? AND status='CURRENT'""",
        (cik, metric, period_end),
    ).fetchone()
    return row is not None and (
        row["value"] == value
        and row["data_status"] == data_status
        and row["reason_code"] == reason_code
        and row["config_fingerprint"] == fingerprint
    )


def _store_metrics(conn, cik, report, fingerprint) -> None:
    """Metrics are append-with-history like concepts (D18): one CURRENT row
    per (cik, metric, period_end), earlier ones SUPERSEDED.

    No accession on a metric row — its provenance is the input concepts,
    linked through metric_inputs, and pinning a multi-input ratio to one
    filing would be arbitrary (same reasoning as composites).
    """
    created_at = _now()
    for m in report.metrics:
        if _metric_unchanged(conn, cik, m.metric, m.end, m.value,
                             m.data_status, m.reason_code, fingerprint):
            continue
        conn.execute(
            """UPDATE metrics SET status='SUPERSEDED'
               WHERE cik=? AND metric=? AND period_end=? AND status='CURRENT'""",
            (cik, m.metric, m.end),
        )
        cur = conn.execute(
            """INSERT INTO metrics
               (cik, metric, period_end, value, unit, data_status, method,
                reason_code, status, config_fingerprint, created_at)
               VALUES (?,?,?,?,?,?,?,?,'CURRENT',?,?)""",
            (cik, m.metric, m.end, m.value,
             m.unit if m.data_status == "CALCULATED" else None,
             m.data_status, m.method, m.reason_code, fingerprint, created_at),
        )
        metric_id = cur.lastrowid
        for input_concept, input_end in m.inputs:
            row = conn.execute(
                """SELECT id FROM concepts
                   WHERE cik=? AND concept=? AND period_end=? AND status='CURRENT'""",
                (cik, input_concept, input_end),
            ).fetchone()
            if row is None:
                raise ValueError(
                    f"metric {m.metric} {m.end} names input {input_concept} "
                    f"{input_end} but no CURRENT concept row exists"
                )
            conn.execute(
                """INSERT OR IGNORE INTO metric_inputs (metric_id, concept_id)
                   VALUES (?,?)""",
                (metric_id, row["id"]),
            )


def _store_integrity(conn, cik, report, fingerprint) -> None:
    """Integrity results keyed by (cik, period_end, check_name) — a re-run
    updates rather than accumulates (D37). The period verdict is not stored:
    store/queries.py derives it."""
    created_at = _now()
    for r in report.results:
        conn.execute(
            """INSERT INTO integrity_results
               (cik, period_end, check_name, outcome, detail, lhs, rhs,
                deviation, config_fingerprint, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(cik, period_end, check_name) DO UPDATE SET
                 outcome=excluded.outcome, detail=excluded.detail,
                 lhs=excluded.lhs, rhs=excluded.rhs,
                 deviation=excluded.deviation,
                 config_fingerprint=excluded.config_fingerprint""",
            (cik, r.period_end, r.check_name, r.outcome, r.detail, r.lhs,
             r.rhs, r.deviation, fingerprint, created_at),
        )


def _score_unchanged(conn, cik, score) -> bool:
    row = conn.execute(
        """SELECT total_score, grade, grade_uncapped, categories_available,
                  config_fingerprint
           FROM scores WHERE cik=? AND period_end=? AND status='CURRENT'""",
        (cik, score.period_end),
    ).fetchone()
    return row is not None and (
        row["total_score"] == score.total_score
        and row["grade"] == score.grade
        and row["grade_uncapped"] == score.grade_uncapped
        and row["categories_available"] == score.categories_available
        and row["config_fingerprint"] == score.config_fingerprint
    )


def _store_scores(conn, cik, scores) -> None:
    """Append-with-history, like concepts and metrics (D18/D47).

    An integrity-FAIL period simply is not in `scores` — the engine produced
    nothing for it (D45), so exclusion is visible as an absent row rather than
    a flag nobody reads.
    """
    created_at = _now()
    for score in scores:
        if _score_unchanged(conn, cik, score):
            continue
        conn.execute(
            """UPDATE scores SET status='SUPERSEDED'
               WHERE cik=? AND period_end=? AND status='CURRENT'""",
            (cik, score.period_end),
        )
        cur = conn.execute(
            """INSERT INTO scores
               (cik, period_end, total_score, grade, grade_uncapped,
                categories_available, grade_capped, cap_binding, status,
                config_fingerprint, created_at)
               VALUES (?,?,?,?,?,?,?,?,'CURRENT',?,?)""",
            (cik, score.period_end, score.total_score, score.grade,
             score.grade_uncapped, score.categories_available,
             int(score.grade_capped), int(score.cap_binding),
             score.config_fingerprint, created_at),
        )
        score_id = cur.lastrowid
        for category in score.categories:
            for comp in category.components:
                conn.execute(
                    """INSERT INTO score_components
                       (score_id, category, metric, value, points, weight,
                        contribution, treatment, reason_code)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (score_id, category.name, comp.metric, comp.value,
                     comp.points, category.weight,
                     None if comp.points is None
                     else comp.points / 10 * category.weight,
                     comp.treatment, comp.reason_code),
                )


def _store_warnings(conn, cik, report, fingerprint) -> None:
    """Warnings keyed by (cik, period_end, indicator) — a re-run updates.

    Evidence links to CONCEPTS, not metrics: a metric-triggered warning cites
    the concepts that fed the metric, reachable through metric_inputs, so
    provenance still bottoms out in facts and filings (D51).
    """
    created_at = _now()
    for w in report.warnings:
        conn.execute(
            """INSERT INTO warnings
               (cik, period_end, indicator, current_value, previous_value,
                change, threshold, base_severity, severity, escalated,
                escalation_reason, warnings_in_period, config_fingerprint,
                created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(cik, period_end, indicator) DO UPDATE SET
                 current_value=excluded.current_value,
                 previous_value=excluded.previous_value,
                 change=excluded.change, threshold=excluded.threshold,
                 base_severity=excluded.base_severity,
                 severity=excluded.severity, escalated=excluded.escalated,
                 escalation_reason=excluded.escalation_reason,
                 warnings_in_period=excluded.warnings_in_period,
                 config_fingerprint=excluded.config_fingerprint""",
            (cik, w.period_end, w.indicator, w.current_value, w.previous_value,
             w.change, w.threshold, w.base_severity, w.severity,
             int(w.escalated), w.escalation_reason, w.warnings_in_period,
             fingerprint, created_at),
        )
        row = conn.execute(
            """SELECT id FROM warnings
               WHERE cik=? AND period_end=? AND indicator=?""",
            (cik, w.period_end, w.indicator),
        ).fetchone()
        for concept in w.evidence_concepts:
            src = conn.execute(
                """SELECT id FROM concepts WHERE cik=? AND concept=?
                   AND period_end=? AND status='CURRENT'""",
                (cik, concept, w.period_end),
            ).fetchone()
            if src is not None:
                conn.execute(
                    """INSERT OR IGNORE INTO warning_evidence
                       (warning_id, concept_id) VALUES (?,?)""",
                    (row["id"], src["id"]),
                )


def _store_events(conn, cik, events) -> None:
    created_at = _now()
    for e in events:
        existing = conn.execute(
            """SELECT 1 FROM data_quality_events
               WHERE cik=? AND code=? AND tag IS ? AND concept IS ?
                 AND period_end IS ? AND accession IS ? AND detail IS ?""",
            (cik, e.code, e.tag, e.concept, e.period_end, e.accession, e.detail),
        ).fetchone()
        if existing is not None:
            continue
        conn.execute(
            """INSERT INTO data_quality_events
               (cik, code, tag, concept, period_end, accession, detail, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (cik, e.code, e.tag, e.concept, e.period_end, e.accession,
             e.detail, created_at),
        )


def _tag_ranks(tag_map) -> dict:
    """(concept, tag) -> position in the candidate list, frozen at store time."""
    if not tag_map:
        return {}
    return {
        (concept, tag): rank
        for concept, candidates in tag_map.items()
        for rank, tag in enumerate(candidates)
    }


def store_company_data(
    conn,
    cik: int,
    name: str,
    selection: SelectionResult,
    mapping: MappingResult,
    ticker: str | None = None,
    sic: str | None = None,
    tag_map: dict | None = None,
    fingerprint: str | None = None,
    fetched_at: str | None = None,
    composites: list | None = None,
    integrity=None,
    metrics=None,
    scores=None,
    trends=None,
    trend_fingerprint=None,
) -> None:
    """Store one company's selected facts, mapped concepts, composite
    concepts and quality events."""
    if fingerprint is None:
        fingerprint = config_fingerprint()
    composites = composites or []
    filled = frozenset((c.concept, c.end) for c in composites)
    _upsert_company(conn, cik, name, ticker, sic)
    _insert_filings(conn, cik, selection)
    _store_facts(conn, cik, selection, fetched_at=fetched_at)
    _store_concepts(conn, cik, mapping, fingerprint, _tag_ranks(tag_map), filled)
    _store_composites(conn, cik, composites, fingerprint)
    events = list(selection.warnings) + list(mapping.warnings)
    if integrity is not None:
        _store_integrity(conn, cik, integrity, fingerprint)
        events += list(integrity.events)
    if metrics is not None:
        _store_metrics(conn, cik, metrics, fingerprint)
        events += list(metrics.events)
    if scores is not None:
        _store_scores(conn, cik, scores)
    if trends is not None:
        _store_warnings(conn, cik, trends, trend_fingerprint)
    _store_events(conn, cik, events)
    conn.commit()
