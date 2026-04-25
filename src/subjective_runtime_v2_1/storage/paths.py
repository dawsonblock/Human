"""Workspace path resolver for Human Runtime storage.

Reads environment variables to determine where the database, run workspaces,
and export directories live.  Defaults to a ``./data`` directory relative to
the current working directory.

Environment variables
---------------------
HUMAN_DATA_DIR
    Root data directory.  Default: ``./data``.
HUMAN_DB_PATH
    Explicit path to the SQLite database file.
    Default: ``{HUMAN_DATA_DIR}/runtime.db``.
HUMAN_ALLOWED_ROOTS
    Colon-separated list of absolute paths that tools are allowed to read/write.
    Default: ``{HUMAN_DATA_DIR}/workspace``.
"""
from __future__ import annotations

import os
from pathlib import Path


class StoragePaths:
    """Resolved, validated storage paths for a Human Runtime instance."""

    def __init__(
        self,
        data_dir: str | Path | None = None,
        db_path: str | Path | None = None,
        allowed_roots: list[str] | None = None,
    ) -> None:
        # Data directory
        env_data = os.environ.get("HUMAN_DATA_DIR")
        raw_data = data_dir or env_data or "./data"
        self.data_dir: Path = Path(raw_data).resolve()

        # Database path
        env_db = os.environ.get("HUMAN_DB_PATH")
        raw_db = db_path or env_db or (self.data_dir / "runtime.db")
        if str(raw_db) == ":memory:":
            self.db_path: Path | str = ":memory:"
        else:
            self.db_path: Path | str = Path(raw_db).resolve()

        # Allowed roots
        if allowed_roots:
            raw_roots = allowed_roots
        elif "HUMAN_ALLOWED_ROOTS" in os.environ:
            # Use os.pathsep (":" on Unix, ";" on Windows)
            env_val = os.environ["HUMAN_ALLOWED_ROOTS"]
            raw_roots = env_val.split(os.pathsep)
            # Check for empty segments in the env var (e.g., "/tmp/a::/tmp/b")
            for segment in raw_roots:
                if not segment or not segment.strip():
                    raise ValueError(f"HUMAN_ALLOWED_ROOTS contains an empty or whitespace segment: {env_val!r}")
        else:
            raw_roots = [str(self.data_dir / "workspace")]

        self.allowed_roots: list[Path] = self._resolve_roots(raw_roots)

    def _resolve_roots(self, raw: list[str]) -> list[Path]:
        resolved: list[Path] = []
        for r in raw:
            if not r or not r.strip():
                raise ValueError("Allowed root cannot be empty or whitespace-only.")
            # PRE-RESOLUTION TRAVERSAL REJECTION
            # Reject if the raw string contains ".." as a path segment
            if ".." in r.replace("\\", "/").split("/"):
                raise ValueError(
                    f"Allowed root rejected — raw path traversal detected: {r!r}"
                )

            p = Path(r).resolve()
            if not _is_safe_path(p):
                raise ValueError(
                    f"Allowed root rejected — resolved path traversal detected: {r!r}"
                )
            resolved.append(p)
        return resolved

    def run_workspace(self, run_id: str) -> Path:
        """Return the per-run workspace directory, creating it if needed."""
        _validate_run_id(run_id)
        p = self.data_dir / "runs" / run_id / "workspace"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def run_exports(self, run_id: str) -> Path:
        """Return the per-run export directory, creating it if needed."""
        _validate_run_id(run_id)
        p = self.data_dir / "runs" / run_id / "exports"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def ensure_data_dir(self) -> None:
        """Create the data directory tree if it does not already exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "workspace").mkdir(parents=True, exist_ok=True)

    @property
    def allowed_roots_str(self) -> list[str]:
        return [str(r) for r in self.allowed_roots]


# ── Helpers ──────────────────────────────────────────────────────────────────


def _is_safe_path(p: Path) -> bool:
    """Reject obvious path traversal patterns."""
    parts = p.parts
    # Resolved absolute paths should never contain '..' after resolution,
    # but guard against symlink escapes by checking the string form.
    return ".." not in str(p)


def _validate_run_id(run_id: str) -> None:
    """Prevent path traversal via run_id."""
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise ValueError(f"Invalid run_id for path resolution: {run_id!r}")
