"""SQLite schema (Task 8, design approved 2026-09-10 with four amendments).

Raw DDL rather than SQLAlchemy models: the CHECK constraints and partial
unique indexes are the point of this schema, and they read clearly in SQL.

Key structural choices (see DECISIONS D18-D20):
- data_status is constrained to the six allowed values at the database level.
- Period identity keys on period_end, never on `fy`, which is stored for
  provenance display only: it is in no key, no FK and no index, so the fy-stamp
  trap is unsupported by the schema rather than merely documented against (D19).
  Fact identity also includes period type — see uq_facts_current (D29).
- Supersession of facts is a relationship (self-FK), never a deletion.
- concepts and metrics are append-with-history: a partial unique index keeps
  one CURRENT row per identity, and config_fingerprint ties each row to the
  settings that produced it (D18).
- Stress tables are deferred to Phase 8 (D20).
"""

import sqlite3

# STRICT tables need SQLite 3.37+ (Python 3.11 normally bundles newer).
SUPPORTS_STRICT = sqlite3.sqlite_version_info >= (3, 37)

_TABLES = [
    # ---------------- provenance chain ----------------
    """
    CREATE TABLE companies (
      cik     INTEGER PRIMARY KEY,
      ticker  TEXT UNIQUE,
      name    TEXT NOT NULL,
      sic     TEXT            -- no source in v1 data; see PROJECT_STATE dependency
    ){strict}
    """,
    """
    CREATE TABLE filings (
      accession TEXT PRIMARY KEY,
      cik       INTEGER NOT NULL REFERENCES companies(cik),
      form      TEXT NOT NULL,
      filed     TEXT NOT NULL,
      fy        INTEGER,      -- filing's fy stamp: provenance display only
      fp        TEXT
    ){strict}
    """,
    """
    CREATE TABLE facts (
      id           INTEGER PRIMARY KEY,
      cik          INTEGER NOT NULL REFERENCES companies(cik),
      accession    TEXT NOT NULL REFERENCES filings(accession),
      tag          TEXT NOT NULL,
      label        TEXT,
      unit         TEXT NOT NULL,
      val          REAL,
      period_start TEXT,      -- NULL = instant fact
      period_end   TEXT NOT NULL,
      fy           INTEGER,   -- stamp; never keyed, never indexed
      fp           TEXT,
      frame        TEXT,
      fetched_at   TEXT,
      status       TEXT NOT NULL
                   CHECK (status IN ('CURRENT','SUPERSEDED','DUPLICATE','UNAVAILABLE')),
      superseded_by_fact_id INTEGER REFERENCES facts(id),
      reason_code  TEXT,
      CHECK ((status = 'SUPERSEDED') = (superseded_by_fact_id IS NOT NULL)),
      CHECK ((status = 'UNAVAILABLE') = (reason_code IS NOT NULL)),
      CHECK (status <> 'UNAVAILABLE' OR val IS NULL)
    ){strict}
    """,
    """
    CREATE TABLE concepts (
      id           INTEGER PRIMARY KEY,
      cik          INTEGER NOT NULL REFERENCES companies(cik),
      concept      TEXT NOT NULL,
      period_start TEXT,
      period_end   TEXT NOT NULL,
      value        REAL,
      unit         TEXT,
      fy           INTEGER,
      fp           TEXT,
      data_status  TEXT NOT NULL CHECK (data_status IN
                   ('REPORTED','CALCULATED','ESTIMATED','ASSUMED',
                    'AI_INTERPRETED','UNAVAILABLE')),
      source_tag      TEXT,
      source_tag_rank INTEGER,
      label        TEXT,
      fact_id      INTEGER REFERENCES facts(id),
      accession    TEXT REFERENCES filings(accession),
      method       TEXT,
      reason_code  TEXT,
      detail       TEXT,
      override_id  INTEGER REFERENCES overrides(id),
      status       TEXT NOT NULL DEFAULT 'CURRENT'
                   CHECK (status IN ('CURRENT','SUPERSEDED')),
      config_fingerprint TEXT NOT NULL,
      created_at   TEXT NOT NULL,
      CHECK ((data_status = 'UNAVAILABLE') = (reason_code IS NOT NULL)),
      CHECK (data_status <> 'UNAVAILABLE' OR value IS NULL),
      CHECK (data_status <> 'REPORTED' OR
             (source_tag IS NOT NULL AND fact_id IS NOT NULL)),
      CHECK (data_status <> 'CALCULATED' OR method IS NOT NULL)
    ){strict}
    """,
    """
    CREATE TABLE concept_inputs (
      concept_id       INTEGER NOT NULL REFERENCES concepts(id),
      input_concept_id INTEGER NOT NULL REFERENCES concepts(id),
      PRIMARY KEY (concept_id, input_concept_id)
    ){strict}
    """,
    """
    CREATE TABLE metrics (
      id          INTEGER PRIMARY KEY,
      cik         INTEGER NOT NULL REFERENCES companies(cik),
      metric      TEXT NOT NULL,
      period_end  TEXT NOT NULL,
      value       REAL,
      unit        TEXT,
      data_status TEXT NOT NULL CHECK (data_status IN
                  ('REPORTED','CALCULATED','ESTIMATED','ASSUMED',
                   'AI_INTERPRETED','UNAVAILABLE')),
      method      TEXT,
      reason_code TEXT,
      accession   TEXT REFERENCES filings(accession),
      override_applied INTEGER NOT NULL DEFAULT 0
                       CHECK (override_applied IN (0,1)),
      override_id INTEGER REFERENCES overrides(id),
      status      TEXT NOT NULL DEFAULT 'CURRENT'
                  CHECK (status IN ('CURRENT','SUPERSEDED')),
      config_fingerprint TEXT NOT NULL,
      created_at  TEXT NOT NULL,
      CHECK ((data_status = 'UNAVAILABLE') = (reason_code IS NOT NULL)),
      CHECK (data_status <> 'UNAVAILABLE' OR value IS NULL),
      CHECK (data_status <> 'CALCULATED' OR method IS NOT NULL),
      CHECK ((override_id IS NOT NULL) = (override_applied = 1))
    ){strict}
    """,
    """
    CREATE TABLE metric_inputs (
      metric_id  INTEGER NOT NULL REFERENCES metrics(id),
      concept_id INTEGER NOT NULL REFERENCES concepts(id),
      PRIMARY KEY (metric_id, concept_id)
    ){strict}
    """,
    # ---------------- analyst layer ----------------
    """
    CREATE TABLE assumptions (
      id             INTEGER PRIMARY KEY,
      cik            INTEGER REFERENCES companies(cik),  -- NULL = global/config
      name           TEXT NOT NULL,
      value          TEXT NOT NULL,
      unit           TEXT,
      reason         TEXT,
      source         TEXT NOT NULL CHECK (source IN ('user','config')),
      effective_date TEXT NOT NULL,
      status         TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active','retired')),
      affects        TEXT    -- JSON array; descriptive, not queried
    ){strict}
    """,
    """
    CREATE TABLE overrides (
      id             INTEGER PRIMARY KEY,
      concept_id     INTEGER NOT NULL REFERENCES concepts(id),
      original_value REAL,
      override_value REAL NOT NULL,
      reason         TEXT NOT NULL,
      author         TEXT NOT NULL,
      created_at     TEXT NOT NULL
    ){strict}
    """,
    # ---------------- outputs layer (Phase 6-7) ----------------
    """
    CREATE TABLE scores (
      id                   INTEGER PRIMARY KEY,
      cik                  INTEGER NOT NULL REFERENCES companies(cik),
      period_end           TEXT NOT NULL,
      total_score          REAL NOT NULL,
      grade                INTEGER NOT NULL CHECK (grade BETWEEN 1 AND 6),
      categories_available INTEGER NOT NULL
                           CHECK (categories_available BETWEEN 0 AND 5),
      grade_capped         INTEGER NOT NULL DEFAULT 0
                           CHECK (grade_capped IN (0,1)),
      created_at           TEXT NOT NULL
    ){strict}
    """,
    """
    CREATE TABLE score_components (
      score_id     INTEGER NOT NULL REFERENCES scores(id),
      category     TEXT NOT NULL,
      metric       TEXT NOT NULL,
      value        REAL,
      points       REAL,
      weight       REAL NOT NULL,
      contribution REAL,
      treatment    TEXT NOT NULL DEFAULT 'scored'
                   CHECK (treatment IN ('scored','dropped_data_gap','evidence_zero')),
      PRIMARY KEY (score_id, category, metric)
    ){strict}
    """,
    """
    CREATE TABLE warnings (
      id             INTEGER PRIMARY KEY,
      cik            INTEGER NOT NULL REFERENCES companies(cik),
      period_end     TEXT NOT NULL,
      indicator      TEXT NOT NULL,
      current_value  REAL,
      previous_value REAL,
      change         REAL,
      threshold      REAL,
      base_severity  TEXT NOT NULL CHECK (base_severity IN ('Low','Medium','High')),
      severity       TEXT NOT NULL CHECK (severity IN ('Low','Medium','High')),
      escalated      INTEGER NOT NULL DEFAULT 0 CHECK (escalated IN (0,1)),
      created_at     TEXT NOT NULL
    ){strict}
    """,
    """
    CREATE TABLE warning_evidence (
      warning_id INTEGER NOT NULL REFERENCES warnings(id),
      concept_id INTEGER NOT NULL REFERENCES concepts(id),
      PRIMARY KEY (warning_id, concept_id)
    ){strict}
    """,
    # ---------------- data quality ----------------
    """
    CREATE TABLE data_quality_events (
      id         INTEGER PRIMARY KEY,
      cik        INTEGER NOT NULL REFERENCES companies(cik),
      code       TEXT NOT NULL,
      tag        TEXT,
      concept    TEXT,
      period_end TEXT,
      accession  TEXT,
      detail     TEXT,
      created_at TEXT NOT NULL
    ){strict}
    """,
]

_INDEXES = [
    "CREATE INDEX idx_filings_cik ON filings(cik)",
    # One CURRENT fact per (company, tag, period type, period end) — supersession
    # is a relationship. `period_start IS NULL` is the period-type discriminator:
    # a duration fact and an instant fact sharing an end date are different facts
    # and both may be CURRENT (D29).
    "CREATE UNIQUE INDEX uq_facts_current"
    " ON facts(cik, tag, period_end, (period_start IS NULL))"
    " WHERE status = 'CURRENT'",
    "CREATE INDEX idx_facts_cik_period ON facts(cik, period_end)",
    "CREATE INDEX idx_facts_accession ON facts(accession)",
    # append-with-history: one CURRENT row per concept identity (D18)
    "CREATE UNIQUE INDEX uq_concepts_current ON concepts(cik, concept, period_end)"
    " WHERE status = 'CURRENT'",
    "CREATE INDEX idx_concepts_concept_period ON concepts(concept, period_end)",
    "CREATE INDEX idx_concepts_quality ON concepts(cik, data_status)",
    "CREATE UNIQUE INDEX uq_metrics_current ON metrics(cik, metric, period_end)"
    " WHERE status = 'CURRENT'",
    "CREATE INDEX idx_metrics_metric_period ON metrics(metric, period_end)",
    "CREATE INDEX idx_scores ON scores(cik, period_end)",
    "CREATE INDEX idx_warnings ON warnings(cik, period_end, severity)",
    "CREATE INDEX idx_dq_events ON data_quality_events(cik, code)",
]


def ddl_statements(strict: bool | None = None) -> list[str]:
    """Every CREATE statement, with or without STRICT table support."""
    if strict is None:
        strict = SUPPORTS_STRICT
    suffix = " STRICT" if strict else ""
    return [t.strip().format(strict=suffix) for t in _TABLES] + list(_INDEXES)


def create_schema(conn, strict: bool | None = None) -> None:
    for statement in ddl_statements(strict):
        conn.execute(statement)
    conn.commit()
