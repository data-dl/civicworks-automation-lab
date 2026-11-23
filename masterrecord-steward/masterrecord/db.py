"""The SQLite store: open it, apply numbered migrations once, and nothing else."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .runkit import utc_now

MIGRATIONS = Path(__file__).resolve().parent.parent / "db" / "migrations"


def connect(path: str | Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def current_version(con: sqlite3.Connection) -> int:
    exists = con.execute("SELECT 1 FROM sqlite_master WHERE name = 'schema_version'").fetchone()
    if not exists:
        return 0
    return con.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]


def migrate(con: sqlite3.Connection, folder: Path = MIGRATIONS) -> list[int]:
    """Apply every NNN_*.sql newer than the database, in order. Returns the versions applied."""
    applied = []
    have = current_version(con)
    for script in sorted(folder.glob("[0-9][0-9][0-9]_*.sql")):
        version = int(script.name[:3])
        if version <= have:
            continue
        con.executescript(script.read_text(encoding="utf-8"))
        con.execute("INSERT INTO schema_version (version, applied_at) VALUES (?, ?)", (version, utc_now()))
        con.commit()
        applied.append(version)
    return applied
