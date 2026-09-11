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
                       reason_code, fingerprint) -> bool:
    """True when the CURRENT row already says exactly this.

    Append-with-history exists to preserve the evidence that a value MOVED
    (D18); re-storing an identical row under identical config moves nothing, so
    it is a no-op rather than a new history entry.
    """
    row = conn.execute(
        """SELECT value, data_status, reason_code, config_fingerprint
           FROM concepts
           WHERE cik=? AND concept=? AND period_end=? AND status='CURRENT'""",
        (cik, concept, period_end),
    ).fetchone()
    return row is not None and (
        row["value"] == value
        and row["data_status"] == data_status
        and row["reason_code"] == reason_code
        and row["config_fingerprint"] == fingerprint
    )


def _supersede_current_concept(conn, cik, concept, period_end) -> None:
    conn.execute(
        """UPDATE concepts SET status='SUPERSEDED'
           WHERE cik=? AND concept=? AND period_end=? AND status='CURRENT'""",
        (cik, concept, period_end),
    )


def _store_concepts(conn, cik, mapping: MappingResult, fingerprint, tag_ranks) -> None:
    created_at = _now()
    for c in mapping.concepts:
        if _concept_unchanged(conn, cik, c.concept, c.end, c.value,
                              c.data_status, None, fingerprint):
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
        if _concept_unchanged(conn, cik, u.concept, u.period_end, None,
                              "UNAVAILABLE", u.reason_code, fingerprint):
            continue
        _supersede_current_concept(conn, cik, u.concept, u.period_end)
        conn.execute(
            """INSERT INTO concepts
               (cik, concept, period_end, data_status, reason_code, status,
                config_fingerprint, created_at)
               VALUES (?,?,?,'UNAVAILABLE',?, 'CURRENT',?,?)""",
            (cik, u.concept, u.period_end, u.reason_code, fingerprint, created_at),
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
) -> None:
    """Store one company's selected facts, mapped concepts and quality events."""
    if fingerprint is None:
        fingerprint = config_fingerprint()
    _upsert_company(conn, cik, name, ticker, sic)
    _insert_filings(conn, cik, selection)
    _store_facts(conn, cik, selection, fetched_at=fetched_at)
    _store_concepts(conn, cik, mapping, fingerprint, _tag_ranks(tag_map))
    _store_events(conn, cik, list(selection.warnings) + list(mapping.warnings))
    conn.commit()
