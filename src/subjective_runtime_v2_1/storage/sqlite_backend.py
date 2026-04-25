"""SQLiteBackend — first-class storage backend for the Human Runtime.

This class extends ``SQLiteRunStore`` with:

- Schema migrations (``storage_meta`` version table, artifact index, extra
  indexes) applied on first open and on upgrade.
- Atomic lifecycle event insertion (``append_lifecycle_event``) that computes
  ``MAX(seq)`` and inserts inside one ``BEGIN IMMEDIATE`` transaction, closing
  the race between lifecycle publishes and cycle commits.
- Artifact indexing (``run_artifacts`` table) mirrored from ``state.artifacts``
  during ``apply_cycle_transition``.
- ``list_artifacts`` that reads from the index first, falling back to
  ``state.artifacts`` for older databases that predate the index.
- ``get_storage_stats`` for the frontend storage card.
- ``export_run_bundle`` delegated to ``storage.export``.

Backward compatibility
----------------------
``SQLiteRunStore`` (in ``state/sqlite_store.py``) is unchanged.  All existing
call sites (``supervisor.py``, ``app.py``, ``events.py``) that already use
``SQLiteRunStore`` continue to work.  New call sites should use
``SQLiteBackend`` which satisfies the ``RunStore`` Protocol.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore
from subjective_runtime_v2_1.storage.migrations import apply_migrations


class SQLiteBackend(SQLiteRunStore):
    """SQLiteRunStore + migrations + atomic lifecycle events + artifact index."""

    def __init__(self, path: str | Path = "runtime.db") -> None:
        # Delegate to parent which calls _init_db()
        super().__init__(path)
        # Run migrations on top of the base schema
        with self._conn() as conn:
            apply_migrations(conn)

    # ── Atomic lifecycle event ───────────────────────────────────────────────

    def append_lifecycle_event(
        self,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Insert a lifecycle event atomically — one transaction, one seq read.

        Unlike the legacy ``get_last_seq()`` + ``append_event()`` pattern this
        method holds a ``BEGIN IMMEDIATE`` transaction for the entire
        read-modify-write so concurrent cycle commits cannot steal the next seq.

        Returns the committed event row dict.
        """
        now = time.time()
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM run_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            next_seq = int(row[0]) + 1

            conn.execute(
                """
                INSERT INTO run_events (run_id, seq, event_type, event_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, next_seq, event_type, json.dumps(payload), now),
            )
            conn.commit()

        return {
            "run_id": run_id,
            "seq": next_seq,
            "type": event_type,
            "payload": payload,
            "created_at": now,
        }

    # ── apply_cycle_transition with artifact mirroring ───────────────────────

    def apply_cycle_transition(self, transition_or_run_id, new_state=None, cycle_events=None, status=None):  # type: ignore[override]
        """Atomic cycle commit + artifact index mirror.

        Delegates the core commit to the parent implementation, then upserts
        ``state.artifacts`` into the ``run_artifacts`` index table inside the
        same logical write window (a second connection after the state commit).

        SQLite serialises all writes so the two operations are ordered
        correctly even without a shared transaction.
        """
        committed = super().apply_cycle_transition(
            transition_or_run_id, new_state, cycle_events, status
        )
        # Mirror artifacts to the index table
        try:
            self._mirror_artifacts(transition_or_run_id)
        except Exception:
            pass  # Never let artifact indexing crash the cycle
        return committed

    def _mirror_artifacts(self, transition_or_run_id) -> None:
        """Upsert state.artifacts into run_artifacts for the given run."""
        from subjective_runtime_v2_1.runtime.transition import CycleTransition

        if isinstance(transition_or_run_id, CycleTransition):
            run_id = transition_or_run_id.run_id
            artifacts = getattr(transition_or_run_id.state, "artifacts", []) or []
        else:
            run_id = transition_or_run_id
            state = self.load_state(run_id)
            artifacts = getattr(state, "artifacts", []) if state else []

        if not artifacts:
            return

        from dataclasses import asdict
        rows = []
        for a in artifacts:
            d = asdict(a) if hasattr(a, "__dataclass_fields__") else (a if isinstance(a, dict) else {})
            if not d.get("id"):
                continue
            rows.append((
                d.get("id", ""),
                run_id,
                d.get("type", ""),
                d.get("title", ""),
                json.dumps(d.get("content", {})),
                json.dumps(d.get("provenance", {})),
                d.get("created_at", time.time()),
                d.get("step_id"),
            ))

        if not rows:
            return

        with self._conn() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO run_artifacts
                    (artifact_id, run_id, type, title, content_json,
                     provenance_json, created_at, step_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()

    # ── Artifact listing ─────────────────────────────────────────────────────

    def list_artifacts(self, run_id: str) -> list[dict[str, Any]]:
        """List artifacts for a run.

        Reads from the ``run_artifacts`` index first.  If the index has no rows
        for this run (older database), falls back to reading ``state.artifacts``
        from the state JSON blob.
        """
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT artifact_id, run_id, type, title,
                       content_json, provenance_json, created_at, step_id
                FROM run_artifacts
                WHERE run_id = ?
                ORDER BY created_at ASC
                """,
                (run_id,),
            ).fetchall()

        if rows:
            return [
                {
                    "id": r[0],
                    "run_id": r[1],
                    "type": r[2],
                    "title": r[3],
                    "content": json.loads(r[4]),
                    "provenance": json.loads(r[5]),
                    "created_at": r[6],
                    "step_id": r[7],
                }
                for r in rows
            ]

        # Fallback: read from state blob
        state = self.load_state(run_id)
        if state is None:
            return []
        artifacts = getattr(state, "artifacts", []) or []
        from dataclasses import asdict
        result = []
        for a in artifacts:
            d = asdict(a) if hasattr(a, "__dataclass_fields__") else (a if isinstance(a, dict) else {})
            result.append(d)
        return result

    # ── Storage statistics ───────────────────────────────────────────────────

    def get_storage_stats(self) -> dict[str, Any]:
        """Return aggregate storage statistics for the frontend storage card."""
        with self._conn() as conn:
            run_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            event_count = conn.execute("SELECT COUNT(*) FROM run_events").fetchone()[0]
            artifact_count = conn.execute(
                "SELECT COUNT(*) FROM run_artifacts"
            ).fetchone()[0]
            schema_row = conn.execute(
                "SELECT value FROM storage_meta WHERE key = 'schema_version'"
            ).fetchone()
            schema_version = int(schema_row[0]) if schema_row else 0

        return {
            "backend": "sqlite",
            "db_path": str(Path(self.path).name),  # basename only — no absolute path leakage
            "schema_version": schema_version,
            "run_count": run_count,
            "event_count": event_count,
            "artifact_count": artifact_count,
        }

    # ── Export ───────────────────────────────────────────────────────────────

    def export_run_bundle(self, run_id: str) -> dict[str, Any]:
        """Assemble a full export bundle for the given run."""
        from subjective_runtime_v2_1.storage.export import export_run_bundle
        return export_run_bundle(self, run_id)
