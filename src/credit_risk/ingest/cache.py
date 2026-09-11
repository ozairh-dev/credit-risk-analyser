"""Raw JSON cache for SEC responses (docs/data-sources.md).

Every cached file is `{"fetched_at": <iso8601 UTC>, "content": <raw response body>}`.
Raw files are never edited after being written — only replaced by a fresh fetch.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from credit_risk import config


def default_max_age() -> timedelta:
    """Cache staleness window, from config/ingestion.yaml (CLAUDE.md rule 6)."""
    return timedelta(hours=config.ingestion()["max_age_hours"])


def read_cache(path: Path, max_age: timedelta = None):
    """Return cached content if `path` exists and is fresh, else None."""
    if not path.exists():
        return None
    if max_age is None:
        max_age = default_max_age()
    cached = json.loads(path.read_text())
    fetched_at = datetime.fromisoformat(cached["fetched_at"])
    # Exclusive: at exactly max_age the window has elapsed and the cache is
    # stale. The comparison is `>=` by decision, not by accident (D31).
    if datetime.now(timezone.utc) - fetched_at >= max_age:
        return None
    return cached["content"]


def write_cache(path: Path, content) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"fetched_at": datetime.now(timezone.utc).isoformat(), "content": content}
    path.write_text(json.dumps(record))
