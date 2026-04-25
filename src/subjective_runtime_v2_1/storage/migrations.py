"""Schema migrations for the Human Runtime SQLite database.

All migrations are idempotent (CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT
EXISTS).  A ``storage_meta`` table tracks the current schema version so future
migrations can be applied incrementally without wiping data.

Usage::

    from subjective_runtime_v2_1.storage.migrations import apply_migrations
    apply_migrations(conn)   # call once after opening a connection
"""
from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

_CURRENT_VERSION = 1


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply all pending migrations to *conn* inside one transaction.

    This function is idempotent — calling it multiple times on the same
    database is safe and produces no duplicate tables or indexes.
    """
    _ensure_meta_table(conn)
    current = _get_version(conn)
    if current < 1:
        _migrate_v1(conn)
    logger.debug("Storage schema at version %d", _get_version(conn))


# ── Internal helpers ─────────────────────────────────────────────────────────


def _ensure_meta_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS storage_meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _get_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT value FROM storage_meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        return 0
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return 0


def _set_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO storage_meta (key, value) VALUES ('schema_version', ?)",
        (str(version),),
    )


def _migrate_v1(conn: sqlite3.Connection) -> None:
    """Initial schema: core tables + artifact index table + extra indexes."""
    logger.info("Applying storage migration v1")

    # Core tables (idempotent — already exist in running databases)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id     TEXT PRIMARY KEY,
            status     TEXT NOT NULL,
            config_json TEXT NOT NULL,
            state_json TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS run_events (
            run_id      TEXT NOT NULL,
            seq         INTEGER NOT NULL,
            event_type  TEXT NOT NULL,
            event_json  TEXT NOT NULL,
            created_at  REAL NOT NULL,
            PRIMARY KEY (run_id, seq)
        )
        """
    )

    # Artifact index table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS run_artifacts (
            artifact_id    TEXT PRIMARY KEY,
            run_id         TEXT NOT NULL,
            type           TEXT NOT NULL,
            title          TEXT NOT NULL,
            content_json   TEXT NOT NULL,
            provenance_json TEXT NOT NULL,
            created_at     REAL NOT NULL,
            step_id        TEXT
        )
        """
    )

    # Indexes
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_run_events_run_id_seq ON run_events(run_id, seq)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_runs_status_updated ON runs(status, updated_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_run_events_type ON run_events(event_type)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_run_events_created_at ON run_events(created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_run_artifacts_run_id ON run_artifacts(run_id)"
    )

    _set_version(conn, 1)
    conn.commit()
    logger.info("Migration v1 complete")
