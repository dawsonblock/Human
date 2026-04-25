import sqlite3
import pytest
from subjective_runtime_v2_1.storage.sqlite_backend import SQLiteBackend

def test_sqlite_pragmas(tmp_path):
    db_path = tmp_path / "pragmas.db"
    db = SQLiteBackend(db_path)
    with db._conn() as conn:
        # Foreign keys
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        
        # Busy timeout
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert timeout == 5000
        
        # Journal mode (should be WAL for file-backed)
        jm = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert jm == "wal"

def test_sqlite_pragmas_memory():
    db = SQLiteBackend(":memory:")
    with db._conn() as conn:
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        
        # Journal mode for :memory: defaults to memory or delete, usually not WAL
        jm = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert jm != "wal"
