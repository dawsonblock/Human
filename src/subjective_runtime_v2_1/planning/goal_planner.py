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
- generic            → echo + memory_write(episode)
"""
from __future__ import annotations

from typing import Any

from subjective_runtime_v2_1.state.models import Goal, Plan, PlanStep
from subjective_runtime_v2_1.util.ids import new_id
from subjective_runtime_v2_1.util.time import now_ts
import json
import logging

logger = logging.getLogger(__name__)

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


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

    if OLLAMA_AVAILABLE and gtype != "operator_request" and gtype != "inspect_workspace" and gtype != "summarize_files" and gtype != "extract_facts" and gtype != "draft_note" and gtype != "propose_write":
        # Dynamic LLM Planning for custom/generic goals
        try:
            system_prompt = """You are an AI planner in a bounded runtime. Your job is to convert a user's goal into a structured JSON array of tool execution steps.
Available tools:
- list_directory (arguments: path)
- append_note (arguments: path, text)
- memory_write (arguments: kind, payload)
- file_write (arguments: path, text)
- write_file_preview (arguments: path, text)
- echo (arguments: message)
- search_files (arguments: path, query)
- file_read (arguments: path)

Return ONLY a valid JSON array of step objects. Each object must have:
- "description": "Short explanation of the step"
- "tool_name": "the exact tool name"
- "arguments": {"key": "value"}

Example Output:
[
  {"description": "Acknowledge goal", "tool_name": "echo", "arguments": {"message": "Started"}},
  {"description": "Read src", "tool_name": "list_directory", "arguments": {"path": "src"}}
]
"""
            res = ollama.chat(model='llama3.2', messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': f"Generate a plan for this goal: {desc}"}
            ])
            
            content = res['message']['content']
            # Find JSON array in the response
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1
            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx:end_idx]
                parsed_steps = json.loads(json_str)
                for step in parsed_steps:
                    steps.append(_step(step.get('description', 'Auto step'), step['tool_name'], step.get('arguments', {})))
                
                stop_conditions = ["Dynamic plan completed"]
                assumptions = ["LLM generated plan is valid"]
                
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
        except Exception as e:
            logger.warning(f"Ollama planning failed: {e}. Falling back to deterministic generic planner.")

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
