"""Tests for the approval request / decision flow.

Acceptance criterion from the problem statement:
  Add POST /runs/{run_id}/approve and POST /runs/{run_id}/deny.
  Those should update the pending request in state, emit approval events, and
  either requeue or discard the held action.
"""
from __future__ import annotations

import asyncio

from subjective_runtime_v2_1.action.contracts import ToolCall, ToolResult, ToolSpec
from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.registry import ToolRegistry
from subjective_runtime_v2_1.action.tools.base import Tool
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.runtime.core import RuntimeCore, CycleResult
from subjective_runtime_v2_1.runtime.events import EventManager, LiveEventBus
from subjective_runtime_v2_1.runtime.scheduler import RuntimeScheduler
from subjective_runtime_v2_1.runtime.supervisor import RunConfig, RunSupervisor
from subjective_runtime_v2_1.state.models import AgentStateV2_1, ActionOption
from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore
from subjective_runtime_v2_1.state.store import InMemoryStateStore
from subjective_runtime_v2_1.util.ids import new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class ConfirmationTool(Tool):
    """A tool that always requires confirmation so we can generate approval requests."""

    spec = ToolSpec(
        name="needs_confirm",
        description="tool that requires human approval",
        input_schema={"type": "object"},
        side_effect_level="high",
        requires_confirmation=True,
    )

    def invoke(self, call: ToolCall, ctx: ExecutionContext) -> ToolResult:
        return ToolResult(ok=True, output={"confirmed": True})


def _make_registry_with_confirm():
    registry = build_tool_registry(allowed_roots=["."])
    registry.register(ConfirmationTool())
    return registry


def _make_runtime_with_confirm():
    registry = _make_registry_with_confirm()
    return RuntimeCore(InMemoryStateStore(), ActionGate(registry), Executor(registry))


# ---------------------------------------------------------------------------
# Unit: approval_requests are recorded in state
# ---------------------------------------------------------------------------

def test_approval_request_recorded_in_state():
    """When gate returns approval_required, an approval_request appears in state."""
    registry = _make_registry_with_confirm()
    gate = ActionGate(registry)
    state = AgentStateV2_1()

    action = ActionOption(
        id=new_id("act"),
        name="do_confirm",
        target={"tool_name": "needs_confirm", "arguments": {}},
        predicted_world_effect={},
        predicted_self_effect={},
        expected_value=0.9,
        estimated_cost=0.01,
        estimated_risk=0.01,
    )

    approved, reason = gate.approve(state, action, idle_tick=False)
    assert approved is False
    assert reason == "approval_required"

    # Simulate what core.py does after gate rejects with approval_required
    req = {
        "action_id": action.id,
        "tool_name": action.target.get("tool_name"),
        "arguments": action.target.get("arguments", {}),
        "reason": action.name,
        "created_at": 0.0,
        "status": "pending",
    }
    state.approval_requests.append(req)

    pending = [r for r in state.approval_requests if r["status"] == "pending"]
    assert len(pending) == 1
    assert pending[0]["tool_name"] == "needs_confirm"


# ---------------------------------------------------------------------------
# Supervisor: approve_action / deny_action
# ---------------------------------------------------------------------------

async def _run_approval_flow(db_path, decision: str):
    db = SQLiteRunStore(db_path)
    events = EventManager(db, LiveEventBus())
    registry = _make_registry_with_confirm()

    def runtime_factory():
        return RuntimeCore(InMemoryStateStore(), ActionGate(registry), Executor(registry))

    scheduler = RuntimeScheduler(runtime_factory, events, db)
    supervisor = await scheduler.create_run("appr1", RunConfig(tick_interval_sec=0.05), {})
    # Let a few cycles run so a needs_confirm action can be queued
    # (planner may not propose it immediately; inject a state that guarantees it)
    await asyncio.sleep(0.05)

    # Manually inject an approval request into persisted state
    state = db.load_state("appr1")
    action_id = new_id("act")
    state.approval_requests.append({
        "action_id": action_id,
        "tool_name": "needs_confirm",
        "arguments": {},
        "reason": "test_approval",
        "created_at": 0.0,
        "status": "pending",
    })
    db.save_state("appr1", state)
    supervisor.runtime.state_store.save("appr1", state)

    if decision == "approve":
        ok = await supervisor.approve_action(action_id)
    else:
        ok = await supervisor.deny_action(action_id)

    await supervisor.stop()
    return ok, db, action_id


def test_approve_action_updates_status(tmp_path):
    ok, db, action_id = asyncio.run(
        _run_approval_flow(tmp_path / "runtime.db", "approve")
    )
    assert ok is True
    state = db.load_state("appr1")
    matched = [r for r in state.approval_requests if r["action_id"] == action_id]
    assert matched
    assert matched[0]["status"] == "approved"


def test_deny_action_updates_status(tmp_path):
    ok, db, action_id = asyncio.run(
        _run_approval_flow(tmp_path / "runtime.db", "deny")
    )
    assert ok is True
    state = db.load_state("appr1")
    matched = [r for r in state.approval_requests if r["action_id"] == action_id]
    assert matched
    assert matched[0]["status"] == "denied"


def test_approve_emits_approval_granted_event(tmp_path):
    _, db, action_id = asyncio.run(
        _run_approval_flow(tmp_path / "runtime.db", "approve")
    )
    event_types = [e["type"] for e in db.load_events("appr1", limit=1000)]
    assert "approval_granted" in event_types


def test_deny_emits_approval_denied_event(tmp_path):
    _, db, action_id = asyncio.run(
        _run_approval_flow(tmp_path / "runtime.db", "deny")
    )
    event_types = [e["type"] for e in db.load_events("appr1", limit=1000)]
    assert "approval_denied" in event_types


def test_approve_nonexistent_action_returns_false(tmp_path):
    async def _run():
        db = SQLiteRunStore(tmp_path / "runtime.db")
        events = EventManager(db, LiveEventBus())

        def runtime_factory():
            return RuntimeCore(
                InMemoryStateStore(),
                ActionGate(build_tool_registry(allowed_roots=["."])),
                Executor(build_tool_registry(allowed_roots=["."])),
            )

        scheduler = RuntimeScheduler(runtime_factory, events, db)
        supervisor = await scheduler.create_run("noact", RunConfig(tick_interval_sec=0.5), {})
        result = await supervisor.approve_action("nonexistent_action_id")
        await supervisor.stop()
        return result

    ok = asyncio.run(_run())
    assert ok is False
