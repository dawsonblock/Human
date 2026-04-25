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
        # Enable WAL for file-backed DBs
        if str(path) != ":memory:":
            with self._conn() as conn:
                conn.execute("PRAGMA journal_mode = WAL")
        # Run migrations on top of the base schema
        with self._conn() as conn:
            apply_migrations(conn)

    @sqlite3.connect.register if hasattr(sqlite3.connect, "register") else None # type: ignore
    @contextmanager
    def _conn(self):
        """Override parent _conn to apply safety pragmas on every connection."""
        conn = sqlite3.connect(self.path, check_same_thread=False)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 5000")
            yield conn
        finally:
            conn.close()

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
        """Fully atomic cycle commit including state, events, and artifact index.

        Implements the transition in a single ``BEGIN IMMEDIATE`` transaction.
        If state serialisation, event insertion, or artifact indexing fails,
        the entire transaction is rolled back.
        """
        from subjective_runtime_v2_1.runtime.transition import CycleTransition, RuntimeEventDraft
        from subjective_runtime_v2_1.state.store import state_to_dict

        # --- resolve arguments ---
        if isinstance(transition_or_run_id, CycleTransition):
            transition = transition_or_run_id
            run_id = transition.run_id
            state = transition.state
            status = status if status is not None else transition.status_override
            events_to_commit = [{"type": d.type, "payload": d.payload} for d in transition.events]
        else:
            run_id = transition_or_run_id
            state = new_state
            raw = list(cycle_events) if cycle_events else []
            events_to_commit = [
                {"type": e.type, "payload": e.payload} if isinstance(e, RuntimeEventDraft) else {"type": e[0], "payload": e[1]}
                for e in raw
            ]

        now = time.time()
        state_payload = json.dumps(state_to_dict(state))
        committed_events: list[dict[str, Any]] = []

        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                # 1. Update run state
                if status is None:
                    conn.execute(
                        'UPDATE runs SET state_json = ?, updated_at = ? WHERE run_id = ?',
                        (state_payload, now, run_id),
                    )
                else:
                    conn.execute(
                        'UPDATE runs SET state_json = ?, status = ?, updated_at = ? WHERE run_id = ?',
                        (state_payload, status, now, run_id),
                    )

                # 2. Append events (reuse parent logic but pass active connection)
                committed_events = self.append_events_tx(conn, run_id, events_to_commit, now=now)

                # 3. Mirror artifacts into the index
                self._mirror_artifacts_tx(conn, run_id, state)

                conn.commit()
            except Exception:
                conn.rollback()
                raise

        return committed_events

    def _mirror_artifacts_tx(self, conn: sqlite3.Connection, run_id: str, state: Any) -> None:
        """Upsert state.artifacts into run_artifacts using the provided transaction."""
        artifacts = getattr(state, "artifacts", []) or []
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

        if rows:
            conn.executemany(
                """
                INSERT OR REPLACE INTO run_artifacts
                    (artifact_id, run_id, type, title, content_json,
                     provenance_json, created_at, step_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def _mirror_artifacts(self, transition_or_run_id) -> None:
        """Legacy non-atomic mirror fallback (unused by apply_cycle_transition)."""
        from subjective_runtime_v2_1.runtime.transition import CycleTransition
        if isinstance(transition_or_run_id, CycleTransition):
            run_id = transition_or_run_id.run_id
            state = transition_or_run_id.state
        else:
            run_id = transition_or_run_id
            state = self.load_state(run_id)
        
        if state:
            with self._conn() as conn:
                self._mirror_artifacts_tx(conn, run_id, state)
                conn.commit()

    # ── Artifact listing ─────────────────────────────────────────────────────

    def list_artifacts(self, run_id: str) -> list[dict[str, Any]]:
        """List artifacts for a run, merging indexed rows with state.artifacts fallback.

        Always reads the latest state JSON and the artifact index, merging them
        by artifact ID to ensure a complete list even if mirroring failed or
        was incomplete in the past.  Prefers indexed rows for overlapping IDs.
        """
        # 1. Read from index
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT artifact_id, run_id, type, title,
                       content_json, provenance_json, created_at, step_id
                FROM run_artifacts
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchall()

        indexed = {
            r[0]: {
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
        }

        # 2. Read from state blob fallback
        state = self.load_state(run_id)
        blob_artifacts = getattr(state, "artifacts", []) if state else []
        from dataclasses import asdict
        
        merged = dict(indexed)
        for a in blob_artifacts:
            d = asdict(a) if hasattr(a, "__dataclass_fields__") else (a if isinstance(a, dict) else {})
            aid = d.get("id")
            if aid and aid not in merged:
                merged[aid] = d

        # 3. Return sorted by created_at
        return sorted(merged.values(), key=lambda x: x.get("created_at", 0))

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
