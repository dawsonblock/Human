"""Tests for run export bundle."""
from __future__ import annotations

import time

import pytest

from subjective_runtime_v2_1.storage.sqlite_backend import SQLiteBackend
from subjective_runtime_v2_1.state.models import AgentStateV2_1
from subjective_runtime_v2_1.runtime.transition import CycleTransition, RuntimeEventDraft


def _make_transition(run_id: str, cycle: int) -> CycleTransition:
    state = AgentStateV2_1(cycle_id=cycle)
    return CycleTransition(
        run_id=run_id,
        cycle_id=cycle,
        state=state,
        events=[RuntimeEventDraft(type="cycle_tick", payload={"cycle": cycle})],
        status_override=None,
    )


def test_export_includes_run_metadata(tmp_path):
    db = SQLiteBackend(tmp_path / "exp.db")
    db.create_run("r1", config={"tick": 0.2})

    bundle = db.export_run_bundle("r1")
    assert bundle["run"]["run_id"] == "r1"
    assert "config" in bundle["run"]


def test_export_includes_full_event_stream_in_seq_order(tmp_path):
    db = SQLiteBackend(tmp_path / "exp2.db")
    db.create_run("r2", config={})

    db.apply_cycle_transition(_make_transition("r2", 1))
    db.append_lifecycle_event("r2", "paused", {})
    db.apply_cycle_transition(_make_transition("r2", 2))

    bundle = db.export_run_bundle("r2")
    seqs = [e["seq"] for e in bundle["events"]]
    assert seqs == sorted(seqs)
    assert len(seqs) == 3  # 2 cycle_tick + 1 paused


def test_export_includes_artifacts(tmp_path):
    db = SQLiteBackend(tmp_path / "exp3.db")
    db.create_run("r3", config={})

    art = {
        "id": "art-x",
        "run_id": "r3",
        "type": "note",
        "title": "Test",
        "content": {"text": "hello"},
        "provenance": {},
        "created_at": time.time(),
        "step_id": None,
    }
    state = AgentStateV2_1(cycle_id=1)
    state.artifacts = [art]  # type: ignore[assignment]
    t = CycleTransition(
        run_id="r3",
        cycle_id=1,
        state=state,
        events=[RuntimeEventDraft(type="cycle_tick", payload={})],
        status_override=None,
    )
    db.apply_cycle_transition(t)

    bundle = db.export_run_bundle("r3")
    assert any(a.get("id") == "art-x" for a in bundle["artifacts"])


def test_export_works_after_restart(tmp_path):
    db_path = tmp_path / "exp4.db"
    db1 = SQLiteBackend(db_path)
    db1.create_run("r4", config={})
    db1.apply_cycle_transition(_make_transition("r4", 1))

    db2 = SQLiteBackend(db_path)
    bundle = db2.export_run_bundle("r4")
    assert bundle["run"]["run_id"] == "r4"
    assert len(bundle["events"]) >= 1


def test_export_has_schema_version(tmp_path):
    db = SQLiteBackend(tmp_path / "exp5.db")
    db.create_run("r5", config={})
    bundle = db.export_run_bundle("r5")
    assert "schema_version" in bundle
    assert isinstance(bundle["schema_version"], int)


def test_export_unknown_run_raises(tmp_path):
    db = SQLiteBackend(tmp_path / "exp6.db")
    with pytest.raises(KeyError, match="run not found"):
        db.export_run_bundle("nonexistent-run-id")
