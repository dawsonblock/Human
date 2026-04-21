"""Regression tests: approval-triggered execution.

Before the fix, approve_action() enqueued {"_approval_granted": action_id}
but RuntimeCore.cycle() had no handler for that signal, so the approved action
was never executed.

After the fix, the cycle processes _approval_granted by looking up the
"approved" request, executing the tool exactly once, and marking the request
"executed" so duplicate signals are no-ops.
"""
from __future__ import annotations

import asyncio

from subjective_runtime_v2_1.action.contracts import ToolCall, ToolResult, ToolSpec
from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.action.tools.base import Tool
from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.runtime.events import EventManager, LiveEventBus
from subjective_runtime_v2_1.runtime.scheduler import RuntimeScheduler
from subjective_runtime_v2_1.runtime.supervisor import RunConfig
from subjective_runtime_v2_1.state.models import AgentStateV2_1
from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore
from subjective_runtime_v2_1.state.store import InMemoryStateStore
from subjective_runtime_v2_1.util.ids import new_id


# ---------------------------------------------------------------------------
# Instrumented tool that records how many times it was invoked
# ---------------------------------------------------------------------------

class CountingTool(Tool):
    """Tool that records each invocation; never requires confirmation itself —
    we'll inject an already-approved request manually."""

    spec = ToolSpec(
        name="counting_tool",
        description="counts invocations",
        input_schema={"type": "object"},
        side_effect_level="low",
        requires_confirmation=False,
    )

    def __init__(self):
        self.call_count = 0

    def invoke(self, call: ToolCall, ctx: ExecutionContext) -> ToolResult:
        self.call_count += 1
        return ToolResult(ok=True, output={"count": self.call_count})


# ---------------------------------------------------------------------------
# Unit: RuntimeCore.cycle() executes approved action when _approval_granted
# ---------------------------------------------------------------------------

def test_cycle_executes_approved_action():
    """_approval_granted in inputs triggers execution of the gated action."""
    tool = CountingTool()
    registry = build_tool_registry(allowed_roots=['.'])
    registry.register(tool)

    runtime = RuntimeCore(InMemoryStateStore(), ActionGate(registry), Executor(registry))

    action_id = new_id("act")
    state = AgentStateV2_1()
    state.approval_requests.append({
        "action_id": action_id,
        "tool_name": "counting_tool",
        "arguments": {},
        "reason": "test_approval",
        "created_at": 0.0,
        "status": "approved",
    })
    runtime.state_store.save("test_run", state)

    transition = runtime.cycle("test_run", {"_approval_granted": action_id})

    assert tool.call_count == 1, "tool must be invoked exactly once after approval"
    assert transition.state.last_outcome is not None
    assert transition.state.last_outcome.get("status") == "ok", \
           f"unexpected outcome: {transition.state.last_outcome}"


def test_cycle_no_double_execution_on_duplicate_signal():
    """Sending _approval_granted twice does not execute the tool a second time."""
    tool = CountingTool()
    registry = build_tool_registry(allowed_roots=['.'])
    registry.register(tool)

    runtime = RuntimeCore(InMemoryStateStore(), ActionGate(registry), Executor(registry))

    action_id = new_id("act")
    state = AgentStateV2_1()
    state.approval_requests.append({
        "action_id": action_id,
        "tool_name": "counting_tool",
        "arguments": {},
        "reason": "test_approval",
        "created_at": 0.0,
        "status": "approved",
    })
    runtime.state_store.save("test_run2", state)

    runtime.cycle("test_run2", {"_approval_granted": action_id})
    assert tool.call_count == 1

    # Second signal — status is now "executed", so the tool must not run again
    runtime.cycle("test_run2", {"_approval_granted": action_id})
    assert tool.call_count == 1, "duplicate approval signal must not execute the tool again"


def test_approval_request_status_becomes_executed():
    """After _approval_granted cycle, the request status transitions to 'executed'."""
    tool = CountingTool()
    registry = build_tool_registry(allowed_roots=['.'])
    registry.register(tool)

    runtime = RuntimeCore(InMemoryStateStore(), ActionGate(registry), Executor(registry))

    action_id = new_id("act")
    state = AgentStateV2_1()
    state.approval_requests.append({
        "action_id": action_id,
        "tool_name": "counting_tool",
        "arguments": {},
        "reason": "test_approval",
        "created_at": 0.0,
        "status": "approved",
    })
    runtime.state_store.save("test_run3", state)

    transition = runtime.cycle("test_run3", {"_approval_granted": action_id})

    matched = [r for r in transition.state.approval_requests if r["action_id"] == action_id]
    assert matched, "approval request must remain in state"
    assert matched[0]["status"] == "executed", \
        f"status must be 'executed' after execution, got: {matched[0]['status']}"


# ---------------------------------------------------------------------------
# Integration: supervisor approve_action → execution persisted in events
# ---------------------------------------------------------------------------

async def _run_integration(db_path):
    db = SQLiteRunStore(db_path)
    events = EventManager(db, LiveEventBus())
    tool = CountingTool()

    def factory():
        registry = build_tool_registry(allowed_roots=['.'])
        registry.register(tool)
        return RuntimeCore(InMemoryStateStore(), ActionGate(registry), Executor(registry))

    scheduler = RuntimeScheduler(factory, events, db)
    supervisor = await scheduler.create_run("appr_exec", RunConfig(tick_interval_sec=0.05), {})
    await asyncio.sleep(0.05)

    # Inject an approved approval request directly into persisted state
    state = db.load_state("appr_exec")
    action_id = new_id("act")
    state.approval_requests.append({
        "action_id": action_id,
        "tool_name": "counting_tool",
        "arguments": {},
        "reason": "integration_test",
        "created_at": 0.0,
        "status": "pending",
    })
    db.save_state("appr_exec", state)
    supervisor.runtime.state_store.save("appr_exec", state)

    # Approve → this should enqueue _approval_granted and trigger execution
    ok = await supervisor.approve_action(action_id)
    assert ok is True

    # Give the loop time to process the queued approval signal
    await asyncio.sleep(0.25)

    await supervisor.stop()
    return db, action_id, tool


def test_approve_triggers_execution(tmp_path):
    db, action_id, tool = asyncio.run(_run_integration(tmp_path / "runtime.db"))
    assert tool.call_count >= 1, "tool must have been executed after approval"

    # Verify the approved request is now marked executed in persisted state
    state = db.load_state("appr_exec")
    matched = [r for r in state.approval_requests if r["action_id"] == action_id]
    assert matched
    assert matched[0]["status"] == "executed", \
        f"persisted status must be 'executed', got: {matched[0]['status']}"


def test_approve_execution_event_persisted(tmp_path):
    """After approval, a tool_call_executed event should appear in the event log."""
    db, action_id, tool = asyncio.run(_run_integration(tmp_path / "runtime.db"))
    event_types = [e["type"] for e in db.load_events("appr_exec", limit=1000)]
    assert "tool_call_executed" in event_types, (
        f"expected tool_call_executed in events, got: {event_types}"
    )
