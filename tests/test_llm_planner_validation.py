"""Tests for LLM planner validation: schema enforcement, unknown tools, fallback."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from subjective_runtime_v2_1.planning.goal_planner import (
    _validate_llm_steps,
    _llm_plan,
    build_plan_for_goal,
)
from subjective_runtime_v2_1.state.models import Goal
from subjective_runtime_v2_1.util.ids import new_id
from subjective_runtime_v2_1.util.time import now_ts


def _goal(description: str, gtype: str = "dynamic_llm") -> Goal:
    return Goal(
        id=new_id("goal"),
        description=description,
        type=gtype,
        priority=1.0,
        created_at=now_ts(),
    )


# ── _validate_llm_steps ──────────────────────────────────────────────────────

def test_valid_steps_accepted():
    raw = [
        {"description": "List src", "tool_name": "list_directory", "arguments": {"path": "src"}},
        {"description": "Echo done", "tool_name": "echo", "arguments": {"message": "done"}},
    ]
    steps, rejections = _validate_llm_steps(raw)
    assert len(steps) == 2
    assert rejections == []


def test_unknown_tool_rejected():
    raw = [
        {"description": "Hack", "tool_name": "run_shell", "arguments": {"cmd": "rm -rf /"}},
    ]
    with pytest.raises(ValueError, match="All LLM steps rejected"):
        _validate_llm_steps(raw)


def test_search_files_old_schema_rejected():
    """LLM returning path/query instead of directory/pattern must be rejected."""
    raw = [
        {"description": "Search", "tool_name": "search_files", "arguments": {"path": ".", "query": "TODO"}},
    ]
    with pytest.raises(ValueError, match="All LLM steps rejected"):
        _validate_llm_steps(raw)


def test_search_files_correct_schema_accepted():
    raw = [
        {"description": "Search", "tool_name": "search_files", "arguments": {"directory": ".", "pattern": "TODO"}},
    ]
    steps, rejections = _validate_llm_steps(raw)
    assert len(steps) == 1
    assert rejections == []


def test_missing_required_arg_rejected():
    raw = [
        # file_write requires both "path" and "text"
        {"description": "Write", "tool_name": "file_write", "arguments": {"path": "out.txt"}},
    ]
    with pytest.raises(ValueError):
        _validate_llm_steps(raw)


def test_partial_rejection_keeps_valid_steps():
    """Mixed batch: valid steps survive even when some are rejected."""
    raw = [
        {"description": "List", "tool_name": "list_directory", "arguments": {"path": "."}},
        {"description": "Bad", "tool_name": "nonexistent_tool", "arguments": {}},
    ]
    steps, rejections = _validate_llm_steps(raw)
    assert len(steps) == 1
    assert len(rejections) == 1


# ── _llm_plan fallback behaviour ─────────────────────────────────────────────

def _make_ollama_response(content: str) -> dict:
    return {"message": {"content": content}}


def test_llm_plan_valid_response():
    payload = json.dumps([
        {"description": "Echo hi", "tool_name": "echo", "arguments": {"message": "hi"}},
    ])
    with patch("subjective_runtime_v2_1.planning.goal_planner._call_ollama_with_timeout",
               return_value=_make_ollama_response(payload)):
        plan = _llm_plan(_goal("say hello"))
    assert plan is not None
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "echo"


def test_llm_plan_malformed_json_falls_back_to_none():
    with patch("subjective_runtime_v2_1.planning.goal_planner._call_ollama_with_timeout",
               return_value=_make_ollama_response("Sure! Here is a plan: not json at all")):
        plan = _llm_plan(_goal("do something"))
    assert plan is None


def test_llm_plan_all_invalid_steps_falls_back_to_none():
    payload = json.dumps([
        {"description": "Bad", "tool_name": "run_shell", "arguments": {"cmd": "ls"}},
    ])
    with patch("subjective_runtime_v2_1.planning.goal_planner._call_ollama_with_timeout",
               return_value=_make_ollama_response(payload)):
        plan = _llm_plan(_goal("do bad thing"))
    assert plan is None


def test_llm_plan_timeout_falls_back_to_none():
    with patch("subjective_runtime_v2_1.planning.goal_planner._call_ollama_with_timeout",
               side_effect=TimeoutError("timed out")):
        plan = _llm_plan(_goal("slow goal"))
    assert plan is None


# ── build_plan_for_goal fallback ─────────────────────────────────────────────

def test_build_plan_falls_back_to_generic_when_llm_unavailable():
    goal = _goal("do something", gtype="dynamic_llm")
    with patch("subjective_runtime_v2_1.planning.goal_planner.OLLAMA_AVAILABLE", False):
        plan = build_plan_for_goal(goal, ["."])
    # Falls back to generic echo+memory_write
    tool_names = [s.tool_name for s in plan.steps]
    assert "echo" in tool_names


def test_build_plan_deterministic_type_skips_llm():
    goal = _goal("list files", gtype="inspect_workspace")
    with patch("subjective_runtime_v2_1.planning.goal_planner._llm_plan") as mock_llm:
        plan = build_plan_for_goal(goal, ["."])
    mock_llm.assert_not_called()
    assert plan.steps[0].tool_name == "list_directory"
