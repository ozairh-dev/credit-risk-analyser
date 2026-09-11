"""The whole path, in one place: raw companyfacts -> stored analysis.

Every stage was built and tested separately (Tasks 6-11). This assembles them
in the one order that is correct — selection, mapping, composites, integrity,
ratios — so the CLI and the real-data tests drive the same sequence rather
than each re-deriving it.
"""

import json

from credit_risk import config
from credit_risk.metrics.composites import compute_composites
from credit_risk.metrics.integrity import run_integrity_checks
from credit_risk.metrics.ratios import compute_metrics
from credit_risk.normalise import map_concepts, select_annual_facts
from credit_risk.store import db
from credit_risk.store.writer import store_company_data


def analyse(raw: dict):
    """Run every stage over one companyfacts payload. No storage, no I/O."""
    selection = select_annual_facts(raw)
    mapping = map_concepts(selection)
    composites = compute_composites(mapping)
    integrity = run_integrity_checks(mapping, composites)
    metrics = compute_metrics(mapping, composites)
    return selection, mapping, composites, integrity, metrics


def analyse_and_store(raw: dict, conn=None, database: str = ":memory:"):
    """Run the pipeline and store the result. Returns (conn, cik)."""
    if conn is None:
        conn = db.create_database(database)
    selection, mapping, composites, integrity, metrics = analyse(raw)
    store_company_data(
        conn, raw["cik"], raw["entityName"], selection, mapping,
        tag_map=config.tag_map(), composites=composites,
        integrity=integrity, metrics=metrics,
    )
    return conn, raw["cik"]


def load_cached(cik: int) -> dict:
    """The cached companyfacts payload for a CIK, or raise a clear error."""
    path = config.RAW_DIR / f"CIK{cik:010d}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No cached companyfacts for CIK {cik} at {path}. "
            f"Run `credit-risk fetch <ticker>` first."
        )
    return json.loads(path.read_text())["content"]
