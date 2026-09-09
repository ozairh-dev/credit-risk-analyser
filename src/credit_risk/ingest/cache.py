"""Raw JSON cache for SEC responses (docs/data-sources.md).

Every cached file is `{"fetched_at": <iso8601 UTC>, "content": <raw response body>}`.
Raw files are never edited after being written — only replaced by a fresh fetch.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_AGE = timedelta(hours=24)


def read_cache(path: Path, max_age: timedelta = MAX_AGE):
    """Return cached content if `path` exists and is fresh, else None."""
    if not path.exists():
        return None
    cached = json.loads(path.read_text())
    fetched_at = datetime.fromisoformat(cached["fetched_at"])
    if datetime.now(timezone.utc) - fetched_at > max_age:
        return None
    return cached["content"]


def write_cache(path: Path, content) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"fetched_at": datetime.now(timezone.utc).isoformat(), "content": content}
    path.write_text(json.dumps(record))
