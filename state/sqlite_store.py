from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
        run_id: str,
        new_state: AgentStateV2_1,
        cycle_events: list[tuple[str, dict[str, Any]]],
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Atomically persist new state and all cycle events in one transaction.

        Returns the list of committed event records (with assigned seqs and
        timestamps) so callers can fan them out to live subscribers without a
        second DB round-trip.
        """
        now = time.time()
        state_payload = json.dumps(state_to_dict(new_state))
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

            row = conn.execute(
                'SELECT COALESCE(MAX(seq), 0) FROM run_events WHERE run_id = ?',
                (run_id,),
            ).fetchone()
            next_seq = int(row[0]) + 1 if row else 1

            for event_type, payload in cycle_events:
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

            conn.commit()

        return committed

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
