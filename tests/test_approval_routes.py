"""Test approval request lifecycle: create → approve/deny → reload → verify.

Acceptance criterion: create a pending approval, approve or deny it,
reload state from SQLite, verify status change + approval event.
"""
from __future__ import annotations

import asyncio

import pytest

from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.runtime.events import EventManager, LiveEventBus
from subjective_runtime_v2_1.runtime.supervisor import RunConfig, RunSupervisor
from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore
from subjective_runtime_v2_1.state.store import InMemoryStateStore
from subjective_runtime_v2_1.util.ids import new_id
from subjective_runtime_v2_1.util.time import now_ts


def _make_supervisor(db_path, run_id="approval_test"):
    db = SQLiteRunStore(db_path)
    em = EventManager(db, LiveEventBus())
    reg = build_tool_registry(allowed_roots=["."])
    db.create_run(run_id, config={}, status="running")

    class StateSeeder:
        def load(self, r):
            state = db.load_state(r)
            if state is None:
                db.create_run(r, config={}, status="running")
                state = db.load_state(r)
            return state
        def save(self, r, state):
            db.save_state(r, state)

    rt = RuntimeCore(StateSeeder(), ActionGate(reg), Executor(reg))
    sv = RunSupervisor(
        run_id=run_id, runtime=rt, events=em,
        config=RunConfig(tick_interval_sec=0.05),
        run_store=db,
    )
    return sv, db, em


def _inject_pending_approval(db, run_id, action_id):
    state = db.load_state(run_id)
    state.approval_requests.append({
        "action_id": action_id,
        "tool_name": "echo",
        "arguments": {"message": "test"},
        "reason": "test_approval",
        "created_at": now_ts(),
        "status": "pending",
    })
    db.save_state(run_id, state)


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------

def test_approve_updates_persisted_status(tmp_path):
    sv, db, _ = _make_supervisor(tmp_path / "approve.db")
    action_id = new_id("act")
    _inject_pending_approval(db, "approval_test", action_id)

    async def _run():
        await sv.start()
        ok = await sv.approve_action(action_id)
        await sv.stop()
        return ok

    granted = asyncio.run(_run())
    assert granted is True

    # Reload from SQLite — status must be 'approved'
    state = db.load_state("approval_test")
    req = next((r for r in state.approval_requests if r["action_id"] == action_id), None)
    assert req is not None
    assert req["status"] == "approved"


def test_approve_emits_approval_granted_event(tmp_path):
    sv, db, _ = _make_supervisor(tmp_path / "approve_ev.db")
    action_id = new_id("act")
    _inject_pending_approval(db, "approval_test", action_id)

    async def _run():
        await sv.start()
        await sv.approve_action(action_id)
        await sv.stop()

    asyncio.run(_run())

    events = db.load_events("approval_test")
    approval_events = [e for e in events if e["type"] == "approval_granted"]
    assert len(approval_events) >= 1
    assert approval_events[0]["payload"]["action_id"] == action_id


# ---------------------------------------------------------------------------
# Deny
# ---------------------------------------------------------------------------

def test_deny_updates_persisted_status(tmp_path):
    sv, db, _ = _make_supervisor(tmp_path / "deny.db")
    action_id = new_id("act")
    _inject_pending_approval(db, "approval_test", action_id)

    async def _run():
        await sv.start()
        ok = await sv.deny_action(action_id)
        await sv.stop()
        return ok

    denied = asyncio.run(_run())
    assert denied is True

    state = db.load_state("approval_test")
    req = next((r for r in state.approval_requests if r["action_id"] == action_id), None)
    assert req is not None
    assert req["status"] == "denied"


def test_deny_emits_approval_denied_event(tmp_path):
    sv, db, _ = _make_supervisor(tmp_path / "deny_ev.db")
    action_id = new_id("act")
    _inject_pending_approval(db, "approval_test", action_id)

    async def _run():
        await sv.start()
        await sv.deny_action(action_id)
        await sv.stop()

    asyncio.run(_run())

    events = db.load_events("approval_test")
    deny_events = [e for e in events if e["type"] == "approval_denied"]
    assert len(deny_events) >= 1
    assert deny_events[0]["payload"]["action_id"] == action_id


def test_approve_nonexistent_returns_false(tmp_path):
    sv, db, _ = _make_supervisor(tmp_path / "noop.db")

    async def _run():
        await sv.start()
        ok = await sv.approve_action("does_not_exist")
        await sv.stop()
        return ok

    result = asyncio.run(_run())
    assert result is False


def test_approve_already_decided_returns_false(tmp_path):
    """Cannot approve an already-denied request."""
    sv, db, _ = _make_supervisor(tmp_path / "double.db")
    action_id = new_id("act")
    _inject_pending_approval(db, "approval_test", action_id)

    async def _run():
        await sv.start()
        await sv.deny_action(action_id)
        second = await sv.approve_action(action_id)  # already denied
        await sv.stop()
        return second

    result = asyncio.run(_run())
    assert result is False
