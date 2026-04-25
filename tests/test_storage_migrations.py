"""Tests for storage schema migrations."""
from __future__ import annotations

import sqlite3

import pytest

from subjective_runtime_v2_1.storage.sqlite_backend import SQLiteBackend
from subjective_runtime_v2_1.storage.migrations import apply_migrations, _get_version


def test_fresh_db_initialises_schema(tmp_path):
    db = SQLiteBackend(tmp_path / "fresh.db")
    with db._conn() as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "runs" in tables
    assert "run_events" in tables
    assert "run_artifacts" in tables
    assert "storage_meta" in tables


def test_fresh_db_schema_version_is_1(tmp_path):
    db = SQLiteBackend(tmp_path / "ver.db")
    stats = db.get_storage_stats()
    assert stats["schema_version"] == 1


def test_reopen_does_not_wipe_data(tmp_path):
    db_path = tmp_path / "persist.db"
    db1 = SQLiteBackend(db_path)
    db1.create_run("run_aaa", config={"x": 1})

    db2 = SQLiteBackend(db_path)
    meta = db2.get_run("run_aaa")
    assert meta is not None
    assert meta.run_id == "run_aaa"


def test_migration_is_idempotent(tmp_path):
    """Applying migrations twice must not raise or wipe data."""
    db_path = tmp_path / "idem.db"
    db = SQLiteBackend(db_path)
    db.create_run("run_idem", config={})

    with db._conn() as conn:
        apply_migrations(conn)   # second application

    assert db.get_run("run_idem") is not None


def test_old_db_without_storage_meta_upgrades(tmp_path):
    """A DB that was created before storage_meta existed must upgrade cleanly."""
    db_path = tmp_path / "old.db"
    # Create a bare-minimum old-style database manually
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY, status TEXT NOT NULL,
            config_json TEXT NOT NULL, state_json TEXT NOT NULL,
            created_at REAL NOT NULL, updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE run_events (
            run_id TEXT NOT NULL, seq INTEGER NOT NULL,
            event_type TEXT NOT NULL, event_json TEXT NOT NULL,
            created_at REAL NOT NULL, PRIMARY KEY (run_id, seq)
        )
        """
    )
    import time, json
    now = time.time()
    conn.execute(
        "INSERT INTO runs VALUES (?, 'running', '{}', '{}', ?, ?)",
        ("run_old", now, now),
    )
    conn.commit()
    conn.close()

    # Opening with SQLiteBackend should run migrations without error
    db = SQLiteBackend(db_path)
    stats = db.get_storage_stats()
    assert stats["schema_version"] == 1
    assert db.get_run("run_old") is not None


def test_extra_indexes_exist(tmp_path):
    db = SQLiteBackend(tmp_path / "idx.db")
    with db._conn() as conn:
        indexes = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
    assert "idx_runs_status_updated" in indexes
    assert "idx_run_events_type" in indexes
    assert "idx_run_events_created_at" in indexes
    assert "idx_run_artifacts_run_id" in indexes


def test_run_artifacts_has_foreign_key(tmp_path):
    db = SQLiteBackend(tmp_path / "fk.db")
    with db._conn() as conn:
        # PRAGMA foreign_key_list(table_name)
        fk_list = conn.execute("PRAGMA foreign_key_list('run_artifacts')").fetchall()
        # Returns list of (id, seq, table, from, to, on_update, on_delete, match)
        assert len(fk_list) > 0
        fk = fk_list[0]
        assert fk[2] == "runs"
        assert fk[3] == "run_id"
        assert fk[4] == "run_id"
        assert fk[6] == "CASCADE"
