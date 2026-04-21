from __future__ import annotations

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall, ToolResult, ToolSpec
from subjective_runtime_v2_1.action.tools.base import Tool

ROUTABLE_KINDS = {"working_note", "episode", "self_history"}


class MemoryWriteTool(Tool):
    spec = ToolSpec(
        name="memory_write",
        description="write a structured memory item into the agent's durable state",
        input_schema={"type": "object", "required": ["kind", "payload"]},
        side_effect_level="low",
        allowed_in_idle=True,
        reversibility="partial",
        observability="high",
        blast_radius="low",
    )

    def invoke(self, call: ToolCall, ctx: ExecutionContext) -> ToolResult:
        kind = call.arguments.get("kind", "")
        payload = call.arguments.get("payload", {})
        if kind not in ROUTABLE_KINDS:
            return ToolResult(
                ok=False,
                output={},
                error=f"unknown memory kind '{kind}'; use one of {sorted(ROUTABLE_KINDS)}",
            )
        entry = {"kind": kind, "payload": payload, "cycle_id": ctx.cycle_id}
        return ToolResult(
            ok=True,
            output={"written": True, "kind": kind},
            memory_writes=[entry],
        )
