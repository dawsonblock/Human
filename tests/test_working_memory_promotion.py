"""Test that working memory is promoted after every cycle.

Acceptance criterion: a multi-cycle run accumulates mixed working-memory
item kinds so AssociativeModule has real inputs to bridge.
"""
from __future__ import annotations

import asyncio

import pytest

from subjective_runtime_v2_1.action.executor import Executor
from subjective_runtime_v2_1.action.gate import ActionGate
from subjective_runtime_v2_1.action.tools import build_tool_registry
from subjective_runtime_v2_1.runtime.core import RuntimeCore, WORKING_MEMORY_CAP
from subjective_runtime_v2_1.state.store import InMemoryStateStore


def _make_runtime():
    reg = build_tool_registry(allowed_roots=["."])
    return RuntimeCore(InMemoryStateStore(), ActionGate(reg), Executor(reg))


def test_working_memory_grows_each_cycle():
    """After 3 cycles, working_memory should have at least 3 items."""
    rt = _make_runtime()
    for _ in range(3):
        t = rt.cycle("r", {"text": "test"})
    state = t.state
    assert len(state.working_memory) >= 3


def test_working_memory_contains_cycle_summary():
    """Each cycle must promote at least a cycle_summary-style packet."""
    rt = _make_runtime()
    t = rt.cycle("r", {"text": "test"})
    state = t.state
    # cycle_summary or focus_summary must appear
    kinds = {w.get("kind") for w in state.working_memory}
    assert kinds & {"cycle_summary", "focus_summary", "tension_summary", "top_hypothesis"}


def test_working_memory_capped_at_limit():
    """working_memory must never exceed WORKING_MEMORY_CAP after many cycles."""
    rt = _make_runtime()
    for i in range(WORKING_MEMORY_CAP * 2):
        rt.cycle("r", {"text": f"tick {i}"})
    state = rt.state_store.load("r")
    assert len(state.working_memory) <= WORKING_MEMORY_CAP


def test_working_memory_mixed_kinds_after_multi_cycle():
    """After several cycles, working_memory should contain at least 2 different kinds."""
    rt = _make_runtime()
    for _ in range(5):
        rt.cycle("r", {"text": "hello", "observed_status": "active"})
    state = rt.state_store.load("r")
    kinds = {w.get("kind") for w in state.working_memory}
    assert len(kinds) >= 2, f"Expected mixed kinds in working_memory, got: {kinds}"


def test_associative_module_gets_real_input():
    """After enough cycles in EXPLORE mode, AssociativeModule should fire."""
    from subjective_runtime_v2_1.state.models import AgentStateV2_1
    from subjective_runtime_v2_1.modules.associative import AssociativeModule

    # Construct a working_memory with two different kinds
    state = AgentStateV2_1()
    state.cognitive_mode = "EXPLORE"
    state.working_memory = [
        {"kind": "focus_summary", "cycle_id": 1},
        {"kind": "tension_summary", "cycle_id": 2},
        {"kind": "top_hypothesis", "cycle_id": 3},
    ]

    module = AssociativeModule()
    candidates = module.run(state, {}, state.interpretive_bias)
    assert len(candidates) >= 1


def test_associative_module_uses_window_of_five():
    """AssociativeModule should use the last 5 working_memory items, not just 2."""
    from subjective_runtime_v2_1.state.models import AgentStateV2_1
    from subjective_runtime_v2_1.modules.associative import AssociativeModule

    state = AgentStateV2_1()
    state.cognitive_mode = "EXPLORE"
    # Put diverse kinds in positions 1-5 (module must see beyond last 2)
    state.working_memory = [
        {"kind": "kind_a", "cycle_id": 1},  # outside old window of 2
        {"kind": "kind_b", "cycle_id": 2},  # outside old window of 2
        {"kind": "kind_a", "cycle_id": 3},
        {"kind": "kind_a", "cycle_id": 4},
        {"kind": "kind_a", "cycle_id": 5},
    ]
    # The last 2 items are the same kind (kind_a), so old code would return [].
    # New code should look at last 5 and find kind_b at position 2.
    module = AssociativeModule()
    candidates = module.run(state, {}, state.interpretive_bias)
    assert len(candidates) >= 1, "AssociativeModule must scan window of 5 to find diverse kinds"


def test_working_memory_cycle_summary_has_cycle_id():
    """Promoted packets must carry the cycle_id they were produced on."""
    rt = _make_runtime()
    t = rt.cycle("r", {"text": "a"})
    t2 = rt.cycle("r", {"text": "b"})
    state = t2.state

    # All promoted items should have a cycle_id > 0
    for item in state.working_memory:
        assert "cycle_id" in item, f"Missing cycle_id in {item}"
        assert item["cycle_id"] >= 1
