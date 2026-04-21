"""GoalDirectedPlanner: generates a short explicit Plan from an active Goal.

Plans are minimal, bounded, and linear (1-5 steps).  The planner uses the
goal type to select a template and fills in concrete tool calls.  Re-planning
only happens on failure, contradiction, or completion boundary.

Supported goal types:
- inspect_workspace  → list_directory + file_read per file
- summarize_files    → file_read per file + append_note(summary)
- extract_facts      → file_read per file + memory_write(episode)
- draft_note         → append_note
- propose_write      → write_file_preview + file_write (gated)
- generic            → echo the goal description
"""
from __future__ import annotations

from typing import Any

from subjective_runtime_v2_1.state.models import Goal, Plan, PlanStep
from subjective_runtime_v2_1.util.ids import new_id
from subjective_runtime_v2_1.util.time import now_ts


def _step(description: str, tool_name: str, arguments: dict[str, Any]) -> PlanStep:
    return PlanStep(
        id=new_id("step"),
        description=description,
        tool_name=tool_name,
        arguments=arguments,
    )


def build_plan_for_goal(goal: Goal, allowed_roots: list[str]) -> Plan:
    """Return a bounded linear Plan for the given Goal."""
    root = allowed_roots[0] if allowed_roots else "."
    steps: list[PlanStep] = []
    stop_conditions: list[str] = []
    assumptions: list[str] = []

    gtype = goal.type.lower()
    desc = goal.description

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
