"""GoalDirectedPlanner: generates a short explicit Plan from an active Goal.

Plans are minimal, bounded, and linear (1-5 steps).  The planner uses the
goal type to select a template and fills in concrete tool calls.  Re-planning
only happens on failure, contradiction, or completion boundary.

Supported goal types:
- inspect_workspace  → list_directory
- summarize_files    → list_directory + append_note(summary)
- extract_facts      → list_directory + memory_write(episode)
- draft_note         → append_note
- propose_write      → write_file_preview + file_write (gated)
- dynamic_llm        → LLM-generated plan via Ollama (with validation)
- generic            → echo + memory_write(episode)
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any

from subjective_runtime_v2_1.state.models import Goal, Plan, PlanStep
from subjective_runtime_v2_1.util.ids import new_id
from subjective_runtime_v2_1.util.time import now_ts

logger = logging.getLogger(__name__)

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

# ──────────────────────────────────────────────────────────────────
# Registered tool schemas: tool_name → required argument keys
# Keep in sync with action/tools/*.py specs.
# ──────────────────────────────────────────────────────────────────
_TOOL_SCHEMAS: dict[str, list[str]] = {
    "list_directory":   ["path"],
    "file_read":        ["path"],
    "file_write":       ["path", "text"],
    "write_file_preview": ["path", "text"],
    "append_note":      ["path", "text"],
    "search_files":     ["directory", "pattern"],   # NOT path/query
    "memory_write":     ["kind", "payload"],
    "echo":             ["message"],
}

_LLM_TIMEOUT_SEC = 20.0  # hard wall-clock limit for ollama.chat()


def _step(description: str, tool_name: str, arguments: dict[str, Any]) -> PlanStep:
    return PlanStep(
        id=new_id("step"),
        description=description,
        tool_name=tool_name,
        arguments=arguments,
    )


def _validate_llm_steps(raw_steps: list[Any]) -> tuple[list[PlanStep], list[str]]:
    """Validate LLM-generated steps against the tool registry.

    Returns (valid_steps, rejection_reasons).  Raises ValueError if no
    steps survive validation.
    """
    valid: list[PlanStep] = []
    rejections: list[str] = []

    for i, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            rejections.append(f"step {i}: not a dict")
            continue

        tool_name = raw.get("tool_name")
        if not isinstance(tool_name, str) or tool_name not in _TOOL_SCHEMAS:
            rejections.append(f"step {i}: unknown tool '{tool_name}'")
            continue

        args = raw.get("arguments", {})
        if not isinstance(args, dict):
            rejections.append(f"step {i}: arguments is not a dict")
            continue

        required = _TOOL_SCHEMAS[tool_name]
        missing = [k for k in required if k not in args]
        if missing:
            rejections.append(
                f"step {i}: tool '{tool_name}' missing required args {missing}"
            )
            continue

        desc = raw.get("description") or f"step {i}"
        valid.append(_step(str(desc), tool_name, args))

    if not valid:
        raise ValueError(f"All LLM steps rejected: {rejections}")

    return valid, rejections


def _call_ollama_with_timeout(model: str, messages: list[dict], timeout: float) -> dict:
    """Run ollama.chat() in a thread with a hard timeout."""
    result: dict[str, Any] = {}
    exc: list[Exception] = []

    def _worker():
        try:
            result["response"] = ollama.chat(model=model, messages=messages)
        except Exception as e:
            exc.append(e)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        raise TimeoutError(f"Ollama did not respond within {timeout}s")
    if exc:
        raise exc[0]
    return result["response"]


def _llm_plan(goal: Goal) -> Plan | None:
    """Try to build a plan via Ollama.  Returns None on any failure."""
    if not OLLAMA_AVAILABLE:
        return None

    system_prompt = (
        "You are an AI planner in a bounded runtime.\n"
        "Convert the user's goal into a JSON array of tool execution steps.\n\n"
        "Available tools and their EXACT required argument keys:\n"
        "- list_directory   → {\"path\": \"<directory>\"}\n"
        "- file_read        → {\"path\": \"<file>\"}\n"
        "- file_write       → {\"path\": \"<file>\", \"text\": \"<content>\"}\n"
        "- write_file_preview → {\"path\": \"<file>\", \"text\": \"<content>\"}\n"
        "- append_note      → {\"path\": \"<file>\", \"text\": \"<content>\"}\n"
        "- search_files     → {\"directory\": \"<dir>\", \"pattern\": \"<regex>\"}\n"
        "- memory_write     → {\"kind\": \"episode\", \"payload\": {\"key\": \"value\"}}\n"
        "- echo             → {\"message\": \"<text>\"}\n\n"
        "Rules:\n"
        "- Only use the tools listed above.  Do NOT invent tool names.\n"
        "- Use EXACTLY the argument keys shown — no aliases (e.g. search_files "
        "uses 'directory' and 'pattern', NOT 'path' or 'query').\n"
        "- Return ONLY a valid JSON array. No prose, no markdown fences.\n\n"
        "Example:\n"
        '[{"description":"List src","tool_name":"list_directory","arguments":{"path":"src"}},'
        '{"description":"Echo done","tool_name":"echo","arguments":{"message":"done"}}]'
    )

    try:
        res = _call_ollama_with_timeout(
            model="llama3.2",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Goal: {goal.description}"},
            ],
            timeout=_LLM_TIMEOUT_SEC,
        )
        content: str = res["message"]["content"]

        # Extract JSON array from response
        start = content.find("[")
        end = content.rfind("]") + 1
        if start == -1 or end == 0:
            logger.warning("Ollama response contained no JSON array")
            return None

        raw_steps = json.loads(content[start:end])
        valid_steps, rejections = _validate_llm_steps(raw_steps)
        if rejections:
            logger.warning("LLM plan had %d rejected steps: %s", len(rejections), rejections)

        return Plan(
            id=new_id("plan"),
            goal_id=goal.id,
            steps=valid_steps,
            assumptions=["LLM-generated plan validated against tool registry"],
            stop_conditions=["dynamic plan completed"],
            current_step=0,
            status="active",
            created_at=now_ts(),
        )

    except TimeoutError as e:
        logger.warning("LLM planner timed out: %s. Using deterministic fallback.", e)
        return None
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning("LLM plan invalid (%s). Using deterministic fallback.", e)
        return None
    except Exception as e:
        logger.warning("LLM planner error: %s. Using deterministic fallback.", e)
        return None


def build_plan_for_goal(goal: Goal, allowed_roots: list[str]) -> Plan:
    """Return a bounded linear Plan for the given Goal."""
    root = allowed_roots[0] if allowed_roots else "."
    steps: list[PlanStep] = []
    stop_conditions: list[str] = []
    assumptions: list[str] = []

    gtype = goal.type.lower()
    desc = goal.description

    # ── Dynamic LLM planning ─────────────────────────────────────────
    # Triggered explicitly via goal type 'dynamic_llm', OR when the goal
    # type is unrecognised and Ollama is available.
    _deterministic_types = {
        "inspect_workspace", "summarize_files", "extract_facts",
        "draft_note", "propose_write", "operator_request",
    }
    if gtype == "dynamic_llm" or (OLLAMA_AVAILABLE and gtype not in _deterministic_types):
        llm_plan = _llm_plan(goal)
        if llm_plan is not None:
            return llm_plan
        # Fall through to generic deterministic fallback

    # ── Deterministic templates ──────────────────────────────────────
    if gtype == "inspect_workspace":
        steps = [
            _step("List workspace contents", "list_directory", {"path": root}),
        ]
        stop_conditions = ["directory listed successfully"]
        assumptions = [f"workspace root is {root}"]

    elif gtype == "summarize_files":
        steps = [
            _step("List files to summarize", "list_directory", {"path": root}),
            _step(
                "Write summary note",
                "append_note",
                {
                    "path": f"{root}/summary.md",
                    "text": f"# Summary\nGoal: {desc}\n\nFiles were listed and noted.\n",
                },
            ),
        ]
        stop_conditions = ["summary written"]
        assumptions = ["files are readable text"]

    elif gtype == "extract_facts":
        steps = [
            _step("List files", "list_directory", {"path": root}),
            _step(
                "Record extraction intent",
                "memory_write",
                {
                    "kind": "episode",
                    "payload": {"event": "extract_facts", "goal": desc, "root": root},
                },
            ),
        ]
        stop_conditions = ["facts recorded"]

    elif gtype == "draft_note":
        steps = [
            _step(
                "Draft note",
                "append_note",
                {
                    "path": f"{root}/draft.md",
                    "text": f"# Draft\n{desc}\n",
                },
            ),
        ]
        stop_conditions = ["note drafted"]

    elif gtype == "propose_write":
        steps = [
            _step(
                "Preview proposed write",
                "write_file_preview",
                {
                    "path": f"{root}/proposed.md",
                    "text": f"# Proposed\n{desc}\n",
                },
            ),
            _step(
                "Apply approved write",
                "file_write",
                {
                    "path": f"{root}/proposed.md",
                    "text": f"# Proposed\n{desc}\n",
                },
            ),
        ]
        stop_conditions = ["write applied or rejected"]
        assumptions = ["operator will review preview before file_write executes"]

    else:
        # Generic fallback: echo the intent and record it
        steps = [
            _step(
                "Acknowledge goal",
                "echo",
                {"message": f"goal:{goal.id}:{desc[:80]}"},
            ),
            _step(
                "Record goal in memory",
                "memory_write",
                {
                    "kind": "episode",
                    "payload": {"event": "goal_acknowledged", "goal_id": goal.id, "description": desc},
                },
            ),
        ]
        stop_conditions = ["goal acknowledged"]

    return Plan(
        id=new_id("plan"),
        goal_id=goal.id,
        steps=steps,
        assumptions=assumptions,
        stop_conditions=stop_conditions,
        current_step=0,
        status="active",
        created_at=now_ts(),
    )
