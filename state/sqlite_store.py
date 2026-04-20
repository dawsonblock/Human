from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from subjective_runtime_v2_1.runtime.transition import CycleTransition, RuntimeEventDraft
from subjective_runtime_v2_1.state.models import AgentStateV2_1
from subjective_runtime_v2_1.state.store import state_from_dict, state_to_dict


@dataclass(slots=True)
class RunMetadata:
    run_id: str
    status: str
    config: dict[str, Any]
    created_at: float
    updated_at: float


class SQLiteRunStore:
    def __init__(self, path: str | Path = 'runtime.db') -> None:
        self.path = str(path)
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path, check_same_thread=False)
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
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
                    run_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (run_id, seq)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_run_events_run_id_seq
                ON run_events(run_id, seq)
                """
            )
            conn.commit()

    def create_run(self, run_id: str, config: dict[str, Any], state: AgentStateV2_1 | None = None, status: str = 'running') -> None:
        now = time.time()
        payload = json.dumps(state_to_dict(state or AgentStateV2_1()))
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, status, config_json, state_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, status, json.dumps(config), payload, now, now),
            )
            conn.commit()

    def has_run(self, run_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute('SELECT 1 FROM runs WHERE run_id = ?', (run_id,)).fetchone()
            return row is not None

    def load_state(self, run_id: str) -> AgentStateV2_1 | None:
        with self._conn() as conn:
            row = conn.execute('SELECT state_json FROM runs WHERE run_id = ?', (run_id,)).fetchone()
            if row is None:
                return None
            return state_from_dict(json.loads(row[0]))

    def save_state(self, run_id: str, state: AgentStateV2_1, status: str | None = None) -> None:
        now = time.time()
        payload = json.dumps(state_to_dict(state))
        with self._conn() as conn:
            if status is None:
                conn.execute(
                    'UPDATE runs SET state_json = ?, updated_at = ? WHERE run_id = ?',
                    (payload, now, run_id),
                )
            else:
                conn.execute(
                    'UPDATE runs SET state_json = ?, status = ?, updated_at = ? WHERE run_id = ?',
                    (payload, status, now, run_id),
                )
            conn.commit()

    def get_run(self, run_id: str) -> RunMetadata | None:
        with self._conn() as conn:
            row = conn.execute(
                'SELECT run_id, status, config_json, created_at, updated_at FROM runs WHERE run_id = ?',
                (run_id,),
            ).fetchone()
            if row is None:
                return None
            return RunMetadata(
                run_id=row[0],
                status=row[1],
                config=json.loads(row[2]),
                created_at=row[3],
                updated_at=row[4],
            )

    def list_runs(self) -> list[RunMetadata]:
        with self._conn() as conn:
            rows = conn.execute(
                'SELECT run_id, status, config_json, created_at, updated_at FROM runs ORDER BY updated_at DESC'
            ).fetchall()
            return [
                RunMetadata(
                    run_id=r[0],
                    status=r[1],
                    config=json.loads(r[2]),
                    created_at=r[3],
                    updated_at=r[4],
                )
                for r in rows
            ]

    def list_recoverable_runs(self) -> list[RunMetadata]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT run_id, status, config_json, created_at, updated_at FROM runs WHERE status IN ('running', 'paused') ORDER BY updated_at DESC"
            ).fetchall()
            return [
                RunMetadata(
                    run_id=r[0],
                    status=r[1],
                    config=json.loads(r[2]),
                    created_at=r[3],
                    updated_at=r[4],
                )
                for r in rows
            ]

    def apply_cycle_transition(
        self,
        transition_or_run_id,
        new_state: AgentStateV2_1 | None = None,
        cycle_events=None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Atomically persist new state and all cycle events in one transaction.

        Accepts either:
        - A ``CycleTransition`` object as the first argument (preferred), or
        - The legacy positional form: ``(run_id, new_state, cycle_events, status)``

        Returns the list of committed event records (with assigned seqs and
        timestamps) so callers can fan them out to live subscribers.
        """
        # --- resolve arguments ---
        if isinstance(transition_or_run_id, CycleTransition):
            transition = transition_or_run_id
            run_id = transition.run_id
            state = transition.state
            status = status if status is not None else transition.status_override
            events_to_commit = [(d.type, d.payload) for d in transition.events]
        else:
            run_id = transition_or_run_id
            state = new_state
            # Handle both (event_type, payload) tuples and RuntimeEventDraft objects
            from subjective_runtime_v2_1.runtime.transition import RuntimeEventDraft  # noqa: F401
            raw = list(cycle_events) if cycle_events else []
            events_to_commit = [
                (e.type, e.payload) if isinstance(e, RuntimeEventDraft) else (e[0], e[1])
                for e in raw
            ]

        now = time.time()
        state_payload = json.dumps(state_to_dict(state))
        committed: list[dict[str, Any]] = []

        with self._conn() as conn:
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

            committed = self.append_events_tx(conn, run_id, [
                {"type": et, "payload": p} for et, p in events_to_commit
            ], now=now)

            conn.commit()

        return committed

    def append_events_tx(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        events: list[dict[str, Any]],
        now: float | None = None,
    ) -> list[dict[str, Any]]:
        """Insert events inside an already-open connection/transaction.

        ``events`` should be a list of dicts with ``type`` and ``payload`` keys.
        Returns the inserted records with ``seq`` and ``created_at`` filled in.
        """
        if now is None:
            now = time.time()
        row = conn.execute(
            'SELECT COALESCE(MAX(seq), 0) FROM run_events WHERE run_id = ?',
            (run_id,),
        ).fetchone()
        next_seq = int(row[0]) + 1 if row else 1
        committed: list[dict[str, Any]] = []
        for evt in events:
            event_type = evt["type"]
            payload = evt["payload"]
            conn.execute(
                'INSERT INTO run_events (run_id, seq, event_type, event_json, created_at) VALUES (?, ?, ?, ?, ?)',
                (run_id, next_seq, event_type, json.dumps(payload), now),
            )
            committed.append({
                'run_id': run_id,
                'seq': next_seq,
                'type': event_type,
                'payload': payload,
                'created_at': now,
            })
            next_seq += 1
        return committed

    def update_run_status(self, run_id: str, status: str) -> None:
        """Update only the status column for a run."""
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                'UPDATE runs SET status = ?, updated_at = ? WHERE run_id = ?',
                (status, now, run_id),
            )
            conn.commit()

    def append_event(self, run_id: str, seq: int, event_type: str, payload: dict[str, Any]) -> float:
        """Persist a single event.  Used by EventManager.publish for lifecycle events."""
        created_at = time.time()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO run_events (run_id, seq, event_type, event_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, seq, event_type, json.dumps(payload), created_at),
            )
            conn.commit()
        return created_at

    def load_events(self, run_id: str, after_seq: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT run_id, seq, event_type, event_json, created_at
                FROM run_events
                WHERE run_id = ? AND seq > ?
                ORDER BY seq ASC
                LIMIT ?
                """,
                (run_id, after_seq, limit),
            ).fetchall()
            return [
                {
                    'run_id': r[0],
                    'seq': r[1],
                    'type': r[2],
                    'payload': json.loads(r[3]),
                    'created_at': r[4],
                }
                for r in rows
            ]

    def get_last_seq(self, run_id: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                'SELECT COALESCE(MAX(seq), 0) FROM run_events WHERE run_id = ?',
                (run_id,),
            ).fetchone()
            return int(row[0]) if row else 0
