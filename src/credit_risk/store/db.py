"""Database connections.

Foreign keys are OFF by default in SQLite and must be enabled per connection,
so every connection must come from here.
"""

import sqlite3

from credit_risk import config
from credit_risk.store.schema import create_schema

DEFAULT_DB_PATH = config.PROJECT_ROOT / "data" / "credit.db"


def connect(path=None) -> sqlite3.Connection:
    """Open a connection with foreign keys enforced."""
    target = ":memory:" if path == ":memory:" else str(path or DEFAULT_DB_PATH)
    if target != ":memory:":
        DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_database(path=None, strict: bool | None = None) -> sqlite3.Connection:
    conn = connect(path)
    create_schema(conn, strict=strict)
    return conn
