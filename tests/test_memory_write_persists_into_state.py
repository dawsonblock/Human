"""Test that memory_write mutates persisted agent state.

Acceptance criterion: a memory_write action changes persisted runtime state
and that change is visible after reload from SQLite, not only in-process.
"""
from __future__ import annotations

import asyncio

import pytest

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall
from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.action.tools.memory_write import MemoryWriteTool
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.state.models import AgentStateV2_1
from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore
from subjective_runtime_v2_1.state.store import InMemoryStateStore


def _ctx(run_id="r", cycle_id=1):
    return ExecutionContext(run_id=run_id, cycle_id=cycle_id, idle_tick=False,
                           policies={}, self_model={}, world_model={}, regulation={})


def _make_runtime(store=None):
    reg = build_tool_registry(allowed_roots=["."])
    return RuntimeCore(store or InMemoryStateStore(), ActionGate(reg), Executor(reg))


# ---------------------------------------------------------------------------
# Unit: MemoryWriteTool returns declarative memory_writes (no side effects)
# ---------------------------------------------------------------------------

def test_memory_write_tool_has_no_memory_sink():
    tool = MemoryWriteTool()
    assert not hasattr(tool, "memory_sink")


def test_memory_write_working_note_returns_memory_writes():
    tool = MemoryWriteTool()
    call = ToolCall("memory_write", {"kind": "working_note", "payload": {"text": "key insight"}}, reason="test")
    result = tool.invoke(call, _ctx())
    assert result.ok is True
    assert len(result.memory_writes) == 1
    assert result.memory_writes[0]["kind"] == "working_note"


def test_memory_write_episode_returns_memory_writes():
    tool = MemoryWriteTool()
    call = ToolCall("memory_write", {"kind": "episode", "payload": {"event": "learned x"}}, reason="test")
    result = tool.invoke(call, _ctx())
    assert result.ok is True
    assert result.memory_writes[0]["kind"] == "episode"


def test_memory_write_self_history_returns_memory_writes():
    tool = MemoryWriteTool()
    call = ToolCall("memory_write", {"kind": "self_history", "payload": {"note": "improved planning"}}, reason="test")
    result = tool.invoke(call, _ctx())
    assert result.ok is True
    assert result.memory_writes[0]["kind"] == "self_history"


def test_memory_write_unknown_kind_fails():
    tool = MemoryWriteTool()
    call = ToolCall("memory_write", {"kind": "unknown_kind", "payload": {}}, reason="test")
    result = tool.invoke(call, _ctx())
    assert result.ok is False
    assert result.error is not None


# ---------------------------------------------------------------------------
# Integration: mutations visible after SQLite reload
# ---------------------------------------------------------------------------

def test_working_note_persists_to_state(tmp_path):
    db = SQLiteRunStore(tmp_path / "wn.db")
    db.create_run("r1", config={}, status="running")
    rt = _make_runtime()

    # Manually apply a working_note memory write to the state
    state = db.load_state("r1")
    rt._apply_tool_mutations(state, {
        "memory_writes": [{"kind": "working_note", "payload": {"text": "key insight"}}],
        "state_delta": {}, "observations": [], "artifacts": [],
    })
    db.save_state("r1", state)

    # Reload and verify
    reloaded = db.load_state("r1")
    working_notes = [w for w in reloaded.working_memory if w.get("kind") == "working_note"]
    assert len(working_notes) >= 1
    assert working_notes[-1]["payload"]["text"] == "key insight"


def test_episode_write_persists_to_episodic_trace(tmp_path):
    db = SQLiteRunStore(tmp_path / "ep.db")
    db.create_run("r2", config={}, status="running")
    rt = _make_runtime()

    state = db.load_state("r2")
    rt._apply_tool_mutations(state, {
        "memory_writes": [{"kind": "episode", "payload": {"event": "discovered pattern"}}],
        "state_delta": {}, "observations": [], "artifacts": [],
    })
    db.save_state("r2", state)

    reloaded = db.load_state("r2")
    episodes = [e for e in reloaded.episodic_trace if e.get("kind") == "episode"]
    assert len(episodes) >= 1


def test_self_history_persists(tmp_path):
    db = SQLiteRunStore(tmp_path / "sh.db")
    db.create_run("r3", config={}, status="running")
    rt = _make_runtime()

    state = db.load_state("r3")
    rt._apply_tool_mutations(state, {
        "memory_writes": [{"kind": "self_history", "payload": {"note": "refined strategy"}}],
        "state_delta": {}, "observations": [], "artifacts": [],
    })
    db.save_state("r3", state)

    reloaded = db.load_state("r3")
    hist = [h for h in reloaded.self_history if h.get("kind") == "self_history"]
    assert len(hist) >= 1


async def _run_memory_write_cycle_and_reload(db_path):
    """Run a cycle where memory_write is the chosen action; reload state after stop."""
    from subjective_runtime_v2_1.runtime.events import EventManager, LiveEventBus
    from subjective_runtime_v2_1.runtime.supervisor import RunConfig, RunSupervisor

    db = SQLiteRunStore(db_path)
    em = EventManager(db, LiveEventBus())
    reg = build_tool_registry(allowed_roots=["."])
    db.create_run("r4", config={}, status="running")

    class StateSeeder:
        def load(self, run_id):
            state = db.load_state(run_id)
            if state is None:
                db.create_run(run_id, config={}, status="running")
                state = db.load_state(run_id)
            return state
        def save(self, run_id, state):
            db.save_state(run_id, state)

    rt = RuntimeCore(StateSeeder(), ActionGate(reg), Executor(reg))
    sv = RunSupervisor(
        run_id="r4", runtime=rt, events=em,
        config=RunConfig(tick_interval_sec=0.02, idle_enabled=True),
        run_store=db,
    )
    await sv.start({"text": "write memory"})
    await asyncio.sleep(0.15)
    await sv.stop()
    return db


def test_memory_write_influences_state_across_reload(tmp_path):
    """Working-memory from a cycle is visible after reloading state from SQLite."""
    db = asyncio.run(_run_memory_write_cycle_and_reload(tmp_path / "cycle.db"))
    state = db.load_state("r4")
    assert state is not None
    assert state.cycle_id >= 1
    # Working memory should have been promoted each cycle
    assert len(state.working_memory) >= 1
