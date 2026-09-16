"""Filing-link derivation (D30b).

D30(b) decided that `source_url` is derived from `(cik, accession)` at export
rather than stored, because a stored copy can only drift: if EDGAR's URL shape
changes, every historic row is silently wrong and needs a migration, whereas a
derived URL is corrected by editing one function.

**This is that one function.** The obligation D30(b) recorded fell due when the
first exporter was built (Phase 9); keeping the derivation in a single place is
the whole point of the decision, so nothing else may build a filing URL.
"""

EDGAR = "https://www.sec.gov/Archives/edgar/data"


def filing_url(cik: int, accession: str) -> str | None:
    """The EDGAR filing-index URL for one accession, or None without one.

    EDGAR's directory segment strips the dashes; the file name keeps them.
    """
    if not accession:
        return None
    return f"{EDGAR}/{int(cik)}/{accession.replace('-', '')}/{accession}-index.htm"
