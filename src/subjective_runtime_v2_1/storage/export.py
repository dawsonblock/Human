"""Run export bundle builder.

Assembles a self-contained JSON bundle for a single run that includes:
- run metadata
- full agent state
- all events in seq order
- all artifacts (from index table if available, else from state)
- export timestamp
- schema version
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from subjective_runtime_v2_1.storage.sqlite_backend import SQLiteBackend

_SCHEMA_VERSION = 1


def export_run_bundle(backend: "SQLiteBackend", run_id: str) -> dict[str, Any]:
    """Return a complete run export bundle as a plain dict (JSON-serialisable)."""
    meta = backend.get_run(run_id)
    if meta is None:
        raise KeyError(f"run not found: {run_id}")

    state = backend.load_state(run_id)
    from subjective_runtime_v2_1.state.store import state_to_dict
    state_dict = state_to_dict(state) if state else {}

    events = backend.load_events(run_id, after_seq=0, limit=100_000)
    artifacts = backend.list_artifacts(run_id)

    from dataclasses import asdict
    return {
        "run": asdict(meta),
        "state": state_dict,
        "events": events,
        "artifacts": artifacts,
        "exported_at": time.time(),
        "schema_version": _SCHEMA_VERSION,
    }
