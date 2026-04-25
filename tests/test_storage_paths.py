"""Tests for StoragePaths: env var config, run workspace, path traversal."""
from __future__ import annotations

import os

import pytest

from subjective_runtime_v2_1.storage.paths import StoragePaths


def test_defaults_use_data_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("HUMAN_DATA_DIR", raising=False)
    monkeypatch.delenv("HUMAN_DB_PATH", raising=False)
    monkeypatch.delenv("HUMAN_ALLOWED_ROOTS", raising=False)
    monkeypatch.chdir(tmp_path)

    paths = StoragePaths()
    assert paths.data_dir.name == "data"
    assert paths.db_path.name == "runtime.db"
    assert "workspace" in str(paths.allowed_roots[0])


def test_human_data_dir_changes_db_location(tmp_path, monkeypatch):
    custom = tmp_path / "custom_data"
    monkeypatch.setenv("HUMAN_DATA_DIR", str(custom))
    monkeypatch.delenv("HUMAN_DB_PATH", raising=False)
    monkeypatch.delenv("HUMAN_ALLOWED_ROOTS", raising=False)

    paths = StoragePaths()
    assert paths.data_dir == custom.resolve()
    assert paths.db_path.parent == custom.resolve()


def test_human_db_path_overrides_default(tmp_path, monkeypatch):
    explicit_db = tmp_path / "mydb.db"
    monkeypatch.setenv("HUMAN_DB_PATH", str(explicit_db))
    monkeypatch.delenv("HUMAN_ALLOWED_ROOTS", raising=False)

    paths = StoragePaths()
    assert paths.db_path == explicit_db.resolve()


def test_db_path_memory_preserved(monkeypatch):
    monkeypatch.setenv("HUMAN_DB_PATH", ":memory:")
    paths = StoragePaths()
    assert paths.db_path == ":memory:"


def test_human_allowed_roots_parsed(tmp_path, monkeypatch):
    r1 = tmp_path / "root1"
    r2 = tmp_path / "root2"
    monkeypatch.setenv("HUMAN_ALLOWED_ROOTS", f"{r1}:{r2}")

    paths = StoragePaths()
    resolved = paths.allowed_roots
    assert any("root1" in str(r) for r in resolved)
    assert any("root2" in str(r) for r in resolved)


def test_run_workspace_inside_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HUMAN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("HUMAN_DB_PATH", raising=False)
    monkeypatch.delenv("HUMAN_ALLOWED_ROOTS", raising=False)

    paths = StoragePaths()
    ws = paths.run_workspace("run_abc123")
    assert ws.exists()
    assert "run_abc123" in str(ws)
    assert str(ws).startswith(str(paths.data_dir))


def test_run_workspace_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setenv("HUMAN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("HUMAN_DB_PATH", raising=False)
    monkeypatch.delenv("HUMAN_ALLOWED_ROOTS", raising=False)

    paths = StoragePaths()
    with pytest.raises(ValueError, match="Invalid run_id"):
        paths.run_workspace("../../etc/passwd")


def test_allowed_roots_rejects_traversal_before_resolution(tmp_path):
    # This should be rejected even if the path doesn't exist or is not absolute yet
    with pytest.raises(ValueError, match="raw path traversal detected"):
        StoragePaths(allowed_roots=["../../etc"])
    
    with pytest.raises(ValueError, match="raw path traversal detected"):
        StoragePaths(allowed_roots=["/safe/path/../etc"])


def test_human_allowed_roots_uses_os_pathsep(tmp_path, monkeypatch):
    import os
    r1 = str(tmp_path / "a")
    r2 = str(tmp_path / "b")
    monkeypatch.setenv("HUMAN_ALLOWED_ROOTS", f"{r1}{os.pathsep}{r2}")
    paths = StoragePaths()
    assert len(paths.allowed_roots) == 2


def test_allowed_roots_str_returns_strings(tmp_path, monkeypatch):
    monkeypatch.setenv("HUMAN_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("HUMAN_DB_PATH", raising=False)
    monkeypatch.delenv("HUMAN_ALLOWED_ROOTS", raising=False)

    paths = StoragePaths()
    for r in paths.allowed_roots_str:
        assert isinstance(r, str)


def test_explicit_args_override_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HUMAN_DATA_DIR", str(tmp_path / "env_data"))
    explicit_db = str(tmp_path / "explicit.db")
    explicit_root = str(tmp_path / "explicit_root")

    paths = StoragePaths(db_path=explicit_db, allowed_roots=[explicit_root])
    assert paths.db_path == (tmp_path / "explicit.db").resolve()
    assert any("explicit_root" in str(r) for r in paths.allowed_roots)
